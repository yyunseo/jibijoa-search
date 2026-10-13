#!/bin/bash
: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID is required}" "${AWS_REGION:=ap-southeast-2}" "${ECR_REPO_NAME:=jibijoa-backend}"
: "${DB_HOST:?DB_HOST is required}" "${QDRANT_HOST:?QDRANT_HOST is required}" "${APP_SECRET_CONFIG_NAME:=prod/backend/secrets}"
: "${CORS_ORIGINS:?CORS_ORIGINS is required (production frontend origins, comma-separated)}"
set -e
echo "Starting docker container..."

# 이전 컨테이너 있으면 중지 후 삭제
sudo docker stop backend 2>/dev/null || true
sudo docker rm backend 2>/dev/null || true

# 컨테이너 실행 (latest 태그 사용)
# DB_PASSWORD는 컨테이너 내부에서 APP_SECRET_CONFIG_NAME을 통해 Secrets Manager에서 가져옴
sudo docker run -d \
  --name backend \
  -p 8000:8000 \
  --restart always \
  -e APP_SECRET_CONFIG_NAME="${APP_SECRET_CONFIG_NAME}" \
  -e DEFAULT_REGION="${AWS_REGION}" \
  -e DB_HOST="${DB_HOST}" \
  -e DB_NAME="project_db" \
  -e DB_USER="backend_user" \
  -e PORT="5432" \
  -e QDRANT_HOST="${QDRANT_HOST}" \
  -e CORS_ORIGINS="${CORS_ORIGINS}" \
  -e QDRANT_PORT="6333" \
  -e QDRANT_COLLECTION_WELCOME_NAME="welcome_subjective_vectors" \
  -e QDRANT_COLLECTION_QPOLL_NAME="qpoll_vectors_v2" \
  -e TRANSFORMERS_CACHE="/home/appuser/.cache/huggingface" \
  -e HF_HOME="/home/appuser/.cache/huggingface" \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest

echo "Container started successfully."

# 컨테이너 상태 확인
sleep 3
sudo docker ps | grep backend

# 컨테이너 로그 확인
echo "Container logs:"
sudo docker logs backend --tail 20