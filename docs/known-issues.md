# 알려진 문제

2026-10 포트폴리오 정리(구조 리팩토링) 중에 발견했지만 **고치지 않은** 문제들이다.
리팩토링은 동작을 바꾸지 않는 것이 원칙이라(`docs/design/` 스펙 §6.2) 버그도 그대로 두고 여기에 기록했다.
줄 번호는 리팩토링 후 기준이다.

## 1. 도달할 수 없는 분기에서 정의되지 않은 변수 참조

- **현상**: `build_sql_from_structured_filters`의 FUZZY/ARRAY 필드 분기 안에 `ott_count` 전용 경로가 있다. 이 경로는 다른 분기에서만 정의되는 `base_condition`을 참조한다.
- **위치**: `app/search/sql_filter.py:130`
- **영향**: 없음. `ott_count`는 `FUZZY_MATCH_FIELDS`와 `ARRAY_FIELDS` 어디에도 없어서 이 줄에 도달하지 않는다. 특성 테스트(`tests/golden/pure_build_sql.json`)에서 `ott_count`가 들어간 모든 케이스가 예외 없이 처리되는 것을 확인했다.
- **처리 계획**: 죽은 분기를 삭제한다. 동작 변화가 없으므로 golden 갱신은 필요 없다.

## 2. Pro 모드 차트 순서가 실행마다 다를 수 있음

- **현상**: 차트를 `ThreadPoolExecutor`로 병렬 생성한 뒤 `as_completed` 완료 순서로 모으고, 우선순위로만 정렬한다. 우선순위가 같은 차트끼리는 완료 순서에 따라 순서가 바뀐다.
- **위치**: `app/insights/analysis.py:329`, `:336`
- **영향**: 같은 질의를 보내도 화면의 차트 순서가 달라질 수 있다. 테스트에서는 비교 전에 차트를 정렬해서 이 비결정성을 흡수한다(`tests/test_api.py`의 `_sorted`).
- **처리 계획**: 정렬 키에 제출 순서를 추가한다 (`(priority, index)`).

## 3. Qdrant 클라이언트를 호출할 때마다 새로 생성

- **현상**: `get_qdrant_client()`는 호출할 때마다 `QdrantClient`를 새로 만든다. 검색 1회에 한 번, 저장소 메서드마다 한 번씩 생성된다.
- **위치**: `app/core/qdrant.py:8`
- **영향**: 요청마다 HTTP 연결을 새로 맺는다. 예전 README는 "Qdrant Client 전역 싱글톤"이라고 설명했지만 사실이 아니었다. 싱글톤인 것은 PostgreSQL 커넥션 풀뿐이다.
- **처리 계획**: 모듈 수준 싱글톤으로 바꾸고 응답 시간을 측정한다.

## 4. 검색 결과 순서가 해시 시드에 따라 달라짐

- **현상**: `hybrid_search`가 결과를 `set`으로 모은 뒤 `list(set)`으로 반환한다. 패널 ID가 문자열이라 순서가 프로세스의 해시 시드에 따라 달라진다.
- **위치**: `app/search/pipeline.py:242`
- **영향**: 같은 질의라도 서버를 재시작하면 결과 테이블의 행 순서가 바뀔 수 있다. 테스트는 `PYTHONHASHSEED=0`으로 고정해서 실행한다.
- **처리 계획**: 재정렬 점수 순서를 유지하도록 리스트로 반환한다.

## 5. 설정에 있는 Qdrant 컬렉션 이름을 코드가 쓰지 않음

- **현상**: `Settings`에 `QDRANT_COLLECTION_WELCOME_NAME`, `QDRANT_COLLECTION_QPOLL_NAME`이 있고 배포 설정도 이 값을 넣지만, 코드는 `"qpoll_vectors_v2"`, `"welcome_subjective_vectors"`를 직접 쓴다.
- **위치**: `app/core/config.py:61-62`, `app/search/pipeline.py:132`, `:136`, `app/panels/repository.py:148`, `:157`, `:163`
- **영향**: 환경변수로 컬렉션을 바꿔도 적용되지 않는다.
- **처리 계획**: 하드코딩된 이름을 설정값으로 바꾼다.

## 6. 호출되지 않는 함수

- `app/query/parser.py:174` `extract_limit_from_query`: 원본(`6a72627`)에서도 호출하는 곳이 없었다. 스펙의 삭제 목록에 없어서 남겨 두었다.
- 참고: 예전 README가 소개한 "DBSCAN 군집화"(`_group_answers_with_vectors`)는 유일한 호출부인 `generate_dynamic_insight`가 어디서도 호출되지 않아 실제 서비스에서 실행되지 않던 코드였다. 리팩토링하면서 둘 다 삭제했다.

## 7. 테스트로 보호되지 않는 영역

리팩토링 후 커버리지는 전체 81%다 (`pytest --cov=app`). 다음 부분은 테스트가 실행하지 않는다.

| 모듈 | 커버리지 | 실행되지 않는 주요 부분 |
|---|---|---|
| `app/core/config.py` | 48% | AWS Secrets Manager에서 비밀 값을 읽는 경로 (테스트는 환경변수 경로만 사용) |
| `app/insights/distributions.py` | 62% | `get_field_distribution_from_db` 전체(전체 DB 기준 집계 SQL), `_extract_core_value`의 템플릿 추출 경로, `_limit_distribution_top_k` |
| `app/insights/analysis.py` | 71% | 대체 필드 매핑(`job_duty_raw` → `job_title_raw` 등), `semantic_conditions` 기반 2차 차트, 1인 가구 분기, 예외 처리 |
| `app/panels/repository.py` | 75% | 저장소 메서드의 예외 처리 경로, `aggregate_field` |
| `app/search/pipeline.py` | 83% | 라우팅 보정(인구통계 → 설문 필드 재설정), 범위형 소득 필터 변환 일부 |

## 8. 테스트를 위해 정규화한 값

다음 값은 원래 동작 자체가 비결정적이라 golden과 비교하기 전에 정렬한다.

- `tests/test_api.py`의 Pro 모드 테스트: 응답의 `charts`, 기록된 SQL 목록, Qdrant 호출 목록, LLM 프롬프트 해시 목록 (2번 문제와 스레드 실행 순서 때문)
