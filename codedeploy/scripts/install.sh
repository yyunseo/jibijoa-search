#!/bin/bash
echo "Pulling latest docker image..."

aws ecr get-login-password --region ap-southeast-2 \
    | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.ap-southeast-2.amazonaws.com

docker pull <AWS_ACCOUNT_ID>.dkr.ecr.ap-southeast-2.amazonaws.com/jibijoa-backend:latest
