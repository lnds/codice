FROM python:3.9

ENV PUTHONBUFFERED 1

ONBUILD RUN set -ex && mkdir /app
ONBUILD RUN set -ex && mkdir /static
ONBUILD RUN set -ex && mkdir /media
ONBUILD RUN set -ex && mkdir /uploads

RUN apt-get update

RUN apt-get install -y locales

COPY ./requirements.txt /requirements.txt

RUN pip install -r /requirements.txt

WORKDIR /app

RUN locale-gen es_CL.UTF-8
ENV LANG es_CL.UTF-8
ENV LANGUAGE es_CL:es
ENV LC_ALL es_CL.UTF-8

ADD . /app
COPY . /app