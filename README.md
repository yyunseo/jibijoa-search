# Jibijoa — 자연어 기반 패널 검색 엔진

"서울, 경기에 사는 OTT 이용하는 젊은층 30명"처럼 자연어로 질문하면, 설문 패널 데이터에서 조건에 맞는 사람을 찾아 표와 차트로 보여주는 백엔드다.
2025년 한성대학교 프리캡스톤 팀 프로젝트다.

- **하이브리드 검색**: 질문을 SQL 조건과 의미 조건으로 나눠 PostgreSQL과 Qdrant 결과를 합친다
- **속도**: 검색 단계 87.8초 → 3.85초 (N+1 호출 제거, 필터 방식 변경, 클라이언트 재사용)
- **리팩토링**: golden 테스트로 동작을 고정한 뒤 도메인 단위 구조로 정리, golden 변경 0회

## 문제

패널 데이터는 성격이 다른 두 종류가 섞여 있다.

- **정형 데이터**: 성별, 출생연도, 지역, 소득처럼 값이 정해진 항목 (PostgreSQL, JSONB)
- **비정형 데이터**: "스트레스를 해소하는 방법은 운동이다" 같은 주관식 응답과 Q-Poll 설문 문장 (Qdrant 벡터)

"20대"는 SQL 조건으로, "운동으로 스트레스를 푸는"은 의미 검색으로 풀어야 한다. 그래서 하나의 질문을 두 종류의 조건으로 나누고, 두 저장소의 결과를 합치는 것이 핵심이다.

## 내 역할

팀 프로젝트에서 **검색과 분석 로직**을 맡았다 (팀 프로젝트 기간 main 브랜치 기준 커밋 81개, merge 제외 40개).

- LLM 질의 파싱 프롬프트와 정형/비정형 조건 분리
- PostgreSQL 1차 필터(JSON 조건 → SQL WHERE 절) + Qdrant 벡터 검색 + 재정렬로 이어지는 하이브리드 검색
- Semantic Router, 부정 조건 필터
- 응답 속도 병목 추적과 개선 (아래 [개발 과정](#개발-과정))
- 검색 결과 통계, 차트, LLM 요약

배포와 인프라(AWS CodeBuild/CodeDeploy, 설정, CORS)는 팀원 `dev-resetok`이, 데이터 적재 파이프라인(엑셀 → JSON → 임베딩 → Qdrant 업로드)은 팀원 `gmlcks`가 별도 저장소에서 맡았다.
원본은 팀 저장소 `capstone-Jibijoa/backend`이고, 이 저장소는 그 히스토리에서 패널 데이터와 인프라 식별자를 지운 사본이다(커밋 해시는 원본과 다름).

## 구조

### 요청 흐름 (`POST /api/search`)

```
api/search.py
 └─ search/service.py ─ query/parser.py        LLM이 질의를 정형 조건 + 의미 조건 + 부정 조건으로 분리
     └─ search/pipeline.py
         ├─ query/router.py                    의미 조건이 어느 필드(설문 문항)에 해당하는지 결정
         ├─ search/sql_filter.py               정형 조건 → SQL WHERE 절 → PostgreSQL 후보
         ├─ search/rerank.py                   후보가 있으면: 후보 전체를 Qdrant에서 가져와 메모리에서 재정렬
         │   또는 Qdrant 벡터 검색              후보가 없으면: 일반 벡터 검색
         └─ search/negative.py                 "없음", "안 함" 같은 부정 응답을 정규식 + 벡터로 제외
 └─ search/display.py, panels/table.py         표시할 컬럼 선택, 결과 테이블 조립
```

`POST /api/search-and-analyze`는 같은 검색 뒤에 `insights/`에서 차트와 LLM 요약을 함께 만든다.

### 폴더

| 폴더 | 책임 |
|---|---|
| `app/api/` | HTTP 엔드포인트와 요청 스키마 |
| `app/search/` | 하이브리드 검색 파이프라인 (SQL 필터, 재정렬, 부정 조건, 결과 표시 필드) |
| `app/query/` | 자연어 → 구조화 (LLM 파서, Semantic Router, 키워드 → 필드 매핑) |
| `app/insights/` | 검색 결과 분포, 차트, LLM 요약 |
| `app/panels/` | 패널 필드 카탈로그, PostgreSQL/Qdrant 저장소, 결과 테이블 조립 |
| `app/core/` | 설정, DB 커넥션 풀, Qdrant 클라이언트, 임베딩(KURE-v1), LLM 클라이언트 |

의존 방향은 `api → search, insights → query → panels → core` 한 방향이다. `tests/test_architecture.py`가 이 규칙을 검사한다.

### 기술 스택

Python 3.11, FastAPI, PostgreSQL(psycopg2 커넥션 풀), Qdrant, LangChain + Anthropic Claude(`claude-sonnet-4-5`), HuggingFace 임베딩 `nlpai-lab/KURE-v1`, pandas, scikit-learn

## 개발 과정

자세한 내용과 커밋 근거는 [`docs/development-history.md`](docs/development-history.md)에 있다.

**1. 속도 — 검색 단계 87.8초 → 3.85초**

처음에는 API 응답이 90초 가까이 걸렸다. 로그로 단계별 시간을 나눠 병목을 하나씩 걷어냈다(수치는 당시 측정 기록 기준).

| 병목 | 해결 | 결과 |
|---|---|---|
| 후보 ID를 100개씩 나눠 Qdrant를 반복 호출 (N+1) | 단일 호출로 통합 | 87.82초 → 17.17초 |
| 단일 호출의 대량 `MatchAny` 필터(약 4,920개 ID) | Qdrant Top-K를 먼저 받고, 교집합은 Python에서 계산 | → 6.09초 |
| 스레드마다 클라이언트와 임베딩을 새로 생성 | 메인 스레드에서 한 번 만들어 전달 | → 3.85초 |

차트 집계까지 병렬화했지만 전체 API는 약 11초에서 멈췄다. 남은 시간은 LLM 호출과 CPU 임베딩이었다.

**2. 정확도 — Top-K를 일부 되돌린 이유**

Top-K + 교집합 방식은 SQL 조건을 만족하는 사람이라도 전역 Top-K 밖에 있으면 결과에서 빠뜨렸다. 그래서 SQL 후보 전체를 가져와 재정렬하는 방식(`app/search/rerank.py`)으로 바꾸고, 후보 수 상한으로 비용을 제한했다. 속도를 위해 버렸던 방식을 누락을 막기 위해 다시 쓴 셈이다.

**3. 구조 — 동작을 고정한 뒤 리팩토링**

평평하게 흩어져 있던 파일을 도메인 단위로 나눴다. 실제 DB 없이 동작을 증명하려고, 가짜 PostgreSQL·Qdrant·LLM·임베딩으로 기존 코드의 검색 결과, 실행 SQL, Qdrant 호출, LLM 프롬프트를 먼저 golden 파일에 기록했다. 리팩토링하는 동안 golden은 한 번도 바뀌지 않았다.

## 실행

### 테스트 (DB와 API 키 없이 실행됨)

```bash
make venv   # uv로 Python 3.11 가상환경 생성, 테스트에 필요 없는 torch 등은 제외
make test   # PYTHONHASHSEED=0으로 pytest 실행
```

### 서버

PostgreSQL과 Qdrant가 필요하다. 원본 패널 데이터는 이 저장소에 포함하지 않는다.

```bash
cp .env.example .env            # 값 채우기
set -a; . ./.env; set +a        # 설정을 import 시점에 셸 환경변수에서 읽으므로 export 필요
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

환경변수 목록과 Docker, AWS CodeBuild/CodeDeploy 배포 설정은 [`docs/deployment.md`](docs/deployment.md)에 있다.

## 한계

- 정확도 개선(재정렬 도입) 이후의 응답 시간은 측정하지 않았다.
- 남은 병목은 LLM 질의 파싱과 CPU 임베딩이다.
- 테스트는 가짜 의존성 기반이라 실제 DB 동작 차이는 잡지 못한다. 그래서 리팩토링은 동작을 바꾸지 않는 변경으로만 한정했다.
- 리팩토링 중 발견했지만 동작 보존을 위해 고치지 않은 문제(결과 순서가 해시 시드에 따라 달라짐, Qdrant 클라이언트를 매번 새로 만듦 등)는 [`docs/known-issues.md`](docs/known-issues.md)에 정리했다.
