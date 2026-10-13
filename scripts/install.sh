#!/bin/bash
: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID is required}" "${AWS_REGION:=ap-southeast-2}" "${ECR_REPO_NAME:=jibijoa-backend}"
set -e

echo "Pulling docker image..."

# ECR 로그인
aws ecr get-login-password --region ${AWS_REGION} \
    | sudo docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

sudo docker rmi ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest --force 2>/dev/null || true

# 이미지 pull
sudo docker pull ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest

echo "Image pulled successfully."