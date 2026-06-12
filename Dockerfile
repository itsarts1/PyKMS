# Dockerfile for py-kms

FROM python:2-alpine
MAINTAINER Arts <itsarts@icloud.com>

ADD . /kms

EXPOSE 1688

CMD ["python", "/kms/server.py"]
