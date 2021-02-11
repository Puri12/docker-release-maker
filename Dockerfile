FROM python:3.7-alpine3.9
MAINTAINER Dave Chevell

WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/requirements.txt
RUN apk add --no-cache git \
    && pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

npm install -g snyk
# the snyk token should be replaced with the atlassian token
snyk auth a36f3f8d-b9b7-4eeb-b07b-079332ef9318