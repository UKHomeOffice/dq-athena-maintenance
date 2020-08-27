ARG PYTHON_ALPINE_VERSION=${PYTHON_ALPINE_VERSION}

FROM quay.io/ukhomeofficedigital/dq-python-alpine:${PYTHON_ALPINE_VERSION}

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
