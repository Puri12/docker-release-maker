FROM python:3.7-alpine3.9
MAINTAINER Dave Chevell

WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app