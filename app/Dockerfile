FROM python:3.6

ENV USERMAP_UID 1000
WORKDIR /APP

RUN mkdir -p /APP/scripts

COPY scripts/ /APP/scripts/

RUN apt-get -y --quiet update && \
    apt-get -y --quiet upgrade

RUN groupadd -r runner && \
    useradd --no-log-init -u $USERMAP_UID -r -g runner runner && \
    groupadd docker && \
    usermod -aG docker runner && \
    chown -R runner:runner /APP
RUN chmod +x scripts/athena_partition_archive.py

RUN pip install boto3

USER ${USERMAP_UID}

CMD python scripts/athena_partition_archive.py
