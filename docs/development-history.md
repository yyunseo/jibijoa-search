# 개발 히스토리

> 팀 프로젝트 Jibijoa(2025 프리캡스톤)에서 내가 맡은 **자연어 검색과 분석 백엔드**의 변화 과정이다.
> 이 저장소는 팀 저장소 `capstone-Jibijoa/backend`의 히스토리를 그대로 가져와서 패널 데이터와 인프라 식별자만 지운 것이다.
> 그래서 커밋 해시가 원본과 다르다. 아래 링크는 이 저장소의 새 해시이고, 괄호 안은 팀 저장소의 원래 해시다.

## 한눈에 보기

| 단계 | 기간 | 한 일 | 결과 |
|---|---|---|---|
| P0 | 2025-10-15 ~ 10-28 | LLM + PostgreSQL로 첫 검색 | 자연어 → SQL 조건 |
| P1 | 11-01 ~ 11-10 | Qdrant 벡터 검색 도입, 하이브리드 검색 | 정형 + 비정형 조건 결합 |
| P2 | 11-14 ~ 11-15 | 응답 속도 병목 추적 | 검색 단계 87.8초 → 3.85초, 전체 API 약 11초 |
| P3 | 11-18 ~ 11-26 | 정확도 개선, Top-K 방식 일부 포기 | 누락 방지를 위해 후보 전수 재정렬 |
| P4·P5 | 11-26 ~ 11-27 | 계층 분리 시도 | dev 브랜치에서 시작, main에는 일부만 반영 |
| P6 | 2026-10 | 구조 리팩토링 | 특성 테스트로 동작을 고정한 뒤 도메인 단위 구조로 리팩토링 |

## P0. 첫 검색 (2025-10-15 ~ 10-28)

- 자연어 질의를 LLM(Bedrock의 Claude)이 정형 조건과 비정형 조건으로 나누고, 정형 조건을 PostgreSQL로 검색하는 구조로 시작했다.
- 근거: [f5b9472][repo-f5b9472] (`e0021de`) 검색 로직 초기 버전, [d84ad0a][repo-d84ad0a] (`817bf90`) 하이브리드 검색 추가, [70043b1][repo-70043b1] (`f75eaa5`) 엔드투엔드 파이프라인 완성

## P1. Qdrant 도입 (11-01 ~ 11-10)

- 주관식 응답과 Q-Poll 설문을 Qdrant에 벡터로 넣고, KURE-v1 한국어 임베딩으로 의미 검색을 붙였다.
- 근거: [0f94aef][repo-0f94aef] (`b6028fe`) LangChain 기반 하이브리드 검색 API, [785d084][repo-785d084] (`0be563a`) 키워드 검색용 SQL, [5f61c7d][repo-5f61c7d] (`71d4b86`) 요청한 인원 수만큼 반환

## P2. 속도: 검색 단계 87.8초 → 3.85초 (11-14 ~ 11-15)

수치 출처: 개인 Notion "API 응답 속도 최적화 보고서". 테스트 질의는 "서울, 경기 OTT 이용하는 젊은층 30명"이다. 수치는 당시 로그 기준이며, 이 저장소의 테스트로 다시 측정한 값이 아니다.

먼저 로그로 단계별 소요 시간을 나눠 봤다. Welcome 주관식 검색 51초, Q-Poll 검색 35초, 병렬 검색 전체 87.82초였다.

| 단계 | 문제 (근거) | 해결 | 결과 |
|---|---|---|---|
| 1 | 후보 ID를 100개씩 나눠 Qdrant `search()`를 반복 호출 (N+1, 컬렉션마다 약 50회) | 반복 호출을 후보 전체를 `MatchAny` 필터로 넘기는 단일 `search()` 호출로 통합 — [592c586][repo-592c586] (`f01ce2b`) | 87.82초 → 17.17초 |
| 2 | 단일 호출이 약 4,920개 ID의 `MatchAny` 필터를 처리하는 데 9~10초 소요 | Qdrant에서 필터 없이 Top-K를 먼저 가져오고, PostgreSQL 후보와의 교집합은 Python에서 계산 — [f367213][repo-f367213] (`5ccb6dc`) | 17.17초 → 6.09초 |
| 3 | Qdrant 호출은 약 1초인데 병렬 검색 전체는 6초. 스레드마다 클라이언트와 임베딩을 새로 만들고 있었음 | 메인 스레드에서 클라이언트와 질의 임베딩을 한 번만 만들어 `ThreadPoolExecutor`의 각 작업에 전달 — [f367213][repo-f367213] (`5ccb6dc`) | 6.09초 → 3.85초 (검색 단계) |
| 4 | 전체 API는 여전히 약 11초. 차트 집계가 순차 실행 | 차트 생성을 `ThreadPoolExecutor`로 병렬화 — [592c586][repo-592c586] (`f01ce2b`)의 `analysis.py` | 차트 2~3초 → 약 1초 |

> 1단계 커밋의 docstring에는 "search_batch 적용"이라고 적혀 있지만, 실제 코드는 Qdrant의 `search_batch()` API가 아니라 `MatchAny` 필터를 쓰는 `search()` 단일 호출이다.

목표는 5초였지만 전체 API는 약 11초에서 멈췄다. 코드 수준의 병목을 걷어내고 나니 남은 시간은 LLM 질의 파싱(약 4초)과 CPU 임베딩이었다. 다음 개선 방향으로 더 가벼운 LLM과 GPU 임베딩을 정리해 두었다.

## P3. 정확도: Top-K를 일부 포기한 이유 (11-18 ~ 11-26)

P2의 Top-K + 교집합 방식에는 약점이 있었다. PostgreSQL 조건을 만족하는 사람이라도 전역 Top-K 안에 들지 못하면 결과에서 빠진다. 예를 들어 "서울 20대" 조건을 만족하는 응답자가 전체 벡터 순위에서 1만 등 밖이면 교집합에서 사라진다.

- 질의 의도에 맞는 필드를 고르는 Semantic Router를 추가했다 — [fb10423][repo-fb10423] (`649dcfd`)
- "없음", "안 함" 같은 부정 응답을 정규식과 벡터 유사도 두 단계로 걸러냈다 — [f19ece1][repo-f19ece1] (`2f7b0c0`). 커밋 메시지는 "검색 로직 성능 수정"이지만 실제 내용은 정확도 작업이다.
- **SQL로 거른 후보 전체를 Qdrant에서 가져와 메모리에서 코사인 유사도로 다시 정렬하는 `rerank_candidates`를 도입했다** — [8b06743][repo-8b06743] (`4fd7664`). 후보가 2,000명 이하이면 질문 매칭도 Python에서 유연하게 처리해서 특수문자 차이로 인한 누락을 막았다. 후보가 10,000명을 넘으면 앞의 5,000명만 재정렬하도록 상한을 두었다.

즉 P2에서 병목이라고 진단하고 버렸던 "후보 ID를 Qdrant 필터로 넘기는" 방식을, 누락을 막기 위해 의도적으로 다시 썼다. 대신 상한(10,000명 초과 시 5,000명)과 분기(2,000명)로 비용을 제한했다.

**이 단계 이후 응답 시간은 측정하지 않았다.** 정확도를 얻은 대가가 얼마인지는 남은 과제다.

## P4·P5. 구조 (11-26 ~ 11-27)

- `app/api, core, services, repositories, schemas` 계층 구조로 나누는 리팩토링을 dev 브랜치에서 진행했다 — [50d086a][repo-50d086a] (`eb6d7ba`) ~ [7dec784][repo-7dec784] (`37912a4`). 마감 때문에 main에는 병합되지 않았고, 이 저장소의 `archive/dev-modularization` 브랜치에 그대로 보존했다.
- main에는 [1a44396][repo-1a44396] (`bf756df`)에서 `repository.py`, `services.py`, `schemas.py`로 나누는 얕은 계층 분리만 들어갔다. 커밋 메시지는 "Revert"지만 실제로는 이 리팩토링과 데이터 파일 삭제가 함께 들어 있다.

## P6. 구조 리팩토링 (2026-10)

- 이 저장소의 히스토리에서 패널 데이터(`welcome_data.json`)와 인프라 식별자(AWS 계정 ID, RDS 주소, 서버 IP, Amplify 도메인)를 모든 커밋에서 지웠다.
- 가짜 PostgreSQL, Qdrant, LLM, 임베딩을 쓰는 특성 테스트로 기존 동작을 golden 파일에 고정한 뒤, 도메인 단위(`query`, `search`, `insights`, `panels`)로 리팩토링했다. 리팩토링 내내 golden은 한 번도 바뀌지 않았다.
- 리팩토링 중에 발견한 문제는 고치지 않고 [`docs/known-issues.md`](known-issues.md)에 기록했다.

[repo-f5b9472]: https://github.com/yyunseo/jibijoa-search/commit/f5b9472bf0b1fcad553a7c80c92e1e6f9cbf53ee
[repo-d84ad0a]: https://github.com/yyunseo/jibijoa-search/commit/d84ad0afb597289c8156d645acad7537fba34bf9
[repo-70043b1]: https://github.com/yyunseo/jibijoa-search/commit/70043b1b76fcb92dd93c7a2966659d31b6530e9a
[repo-0f94aef]: https://github.com/yyunseo/jibijoa-search/commit/0f94aefd37705e7ee59323d570c39eda688ab3bf
[repo-785d084]: https://github.com/yyunseo/jibijoa-search/commit/785d0841e4b07dc1222c9875a9756c5fe60178ae
[repo-5f61c7d]: https://github.com/yyunseo/jibijoa-search/commit/5f61c7d6be89317f56dfa8773c1ac4bb5e5c369e
[repo-592c586]: https://github.com/yyunseo/jibijoa-search/commit/592c586a0c6be1956fb009a17d17ac0324b61922
[repo-f367213]: https://github.com/yyunseo/jibijoa-search/commit/f3672138400690ff8e5f6c56bfdc06a0345d2eb7
[repo-fb10423]: https://github.com/yyunseo/jibijoa-search/commit/fb10423c474ecf2fd094c5700eaf584b2c6ef71f
[repo-f19ece1]: https://github.com/yyunseo/jibijoa-search/commit/f19ece1e9cf3dfd0bafb91960bcbce23bfb934a9
[repo-8b06743]: https://github.com/yyunseo/jibijoa-search/commit/8b067439dbed74fbdea644d82983db88a07e43ac
[repo-50d086a]: https://github.com/yyunseo/jibijoa-search/commit/50d086adf94bba86711bfe684664c626639f7f93
[repo-7dec784]: https://github.com/yyunseo/jibijoa-search/commit/7dec784872513026795ae9e55e8e9ec015e92ca9
[repo-1a44396]: https://github.com/yyunseo/jibijoa-search/commit/1a44396e66b8a6fc48f658cf07381b50b8c22921
