FROM python:3.9-alpine
MAINTAINER Dave Chevell

WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/requirements.txt
RUN apk add --no-cache git npm docker-cli docker-compose jq curl \
    && pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt \
    && npm install -g snyk

COPY . /usr/src/app
