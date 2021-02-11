FROM python:3.7-alpine3.9
MAINTAINER Dave Chevell

WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/requirements.txt
RUN apk add --no-cache git npm \
    && pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

RUN npm install -g snyk
