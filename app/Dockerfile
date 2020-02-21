FROM quay.io/ukhomeofficedigital/python-alpine:3.7.6-alpine3.11

ENV USERMAP_UID 1000
WORKDIR /APP

RUN mkdir -p /APP/scripts

COPY scripts/ /APP/scripts/

RUN apk add --no-cache --quiet --update

RUN adduser -D -H 1000 && \
    chown -R 1000 /APP
RUN chmod +x scripts/athena_partition_archive.py

RUN pip3 install boto3

USER ${USERMAP_UID}

CMD python scripts/athena_partition_archive.py
