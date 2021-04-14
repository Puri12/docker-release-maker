FROM python:3.9-alpine
MAINTAINER Dave Chevell

WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/requirements.txt
RUN apk add --no-cache git npm docker-cli docker-compose curl \
    && pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt \
    && npm install -g snyk

ARG HADOLINT_VERSION=2.1.0
ARG HADOLINT_URL=https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-Linux-x86_64
RUN curl -sL ${HADOLINT_URL} -o /usr/src/app/hadolint \
    && chmod +x /usr/src/app/hadolint

COPY . /usr/src/app
