# 실행과 배포 설정

## 필요한 데이터 저장소

- PostgreSQL: `welcome_meta2` 테이블
- Qdrant: `qpoll_vectors_v2`, `welcome_subjective_vectors` 컬렉션

원본 패널 데이터는 이 저장소에 포함하지 않는다.

## 환경변수

설정은 import 시점에 **셸 환경변수**에서 읽는다. `.env` 파일은 그보다 늦게 로드되므로 직접 실행할 때는 변수를 export해야 한다 ([`known-issues.md`](known-issues.md) 7번). `docker compose`는 `env_file`로 컨테이너 환경변수를 넣어 주므로 `.env`만 있으면 된다.

| 환경변수 | 용도 |
|---|---|
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL 접속 |
| `QDRANT_HOST`, `QDRANT_PORT` | Qdrant 접속 |
| `ANTHROPIC_API_KEY` | LLM |
| `CORS_ORIGINS` | 허용할 프론트엔드 주소 (쉼표로 구분) |
| `APP_SECRET_CONFIG_NAME` | `DB_PASSWORD`가 없을 때 AWS Secrets Manager에서 비밀 값을 읽을 이름 |
| `AWS_ACCOUNT_ID`, `AWS_REGION`, `ECR_REPO_NAME` | 배포 스크립트(`scripts/`, `buildspec.yml`) |

## AWS CodeBuild / CodeDeploy

CodeDeploy 훅(`scripts/install.sh`, `scripts/start.sh`)은 `AWS_ACCOUNT_ID`, `DB_HOST`, `QDRANT_HOST`, `CORS_ORIGINS`가 훅 실행 환경에 없으면 바로 실패한다. CodeDeploy는 env 파일을 자동으로 읽지 않으므로 EC2 인스턴스의 환경(예: 훅을 실행하는 사용자의 셸 프로필)에 미리 설정해야 한다. `buildspec.yml`의 `AWS_ACCOUNT_ID`는 CodeBuild 프로젝트 환경변수로 넣는다.
