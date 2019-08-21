# dq-athena-maintenance

[![Docker Repository on Quay](https://quay.io/repository/ukhomeofficedigital/dq-athena-maintenance "Docker Repository on Quay")](https://quay.io/repository/ukhomeofficedigital/dq-athena-maintenance)

## Introduction
This app archive's tables in Athena and is designed to run in Kubernetes. It utilises Kubernetes `cronjob` that triggers based on the value of `KUBE_SCHEDULE`.

When triggered a job is created which starts a POD, and a container with the image from Quay:-

It currently only supports a rule to archive data that is older than 2 months + current.

A CSV file must exist in S3 which contains the database name, table name and S3 location of the data.

**Note:** The `_archive` table must exist prior to running.

## Dependencies

- Docker
- Kubernetes
- Python3.7
- Drone
- AWS CLI
- Slack
- AWS Keys with access to Athena, Glue and S3

## CSV file
The CSV file must **not** be in utf-8.

The layout of the CSV file is as follows:-

|  database_name  |  table_name  |             s3_location             |
| --------------- | ------------ | ----------------------------------- |
|    database1    |    table1    | s3-bucket/path/to/partition/data/   |
|    database1    |    table2    | s3-bucket/path/to/partition/data/   |
|    database1    |    table3    | s3-bucket/path/to/partition/data/   |
|    database2    |    table1    | s3-bucket/path/to/partition/data/   |
|    database3    |    table1    | s3-bucket/path/to/partition/data/   |

`database_name` - the name of the database (schema).
`table_name` - the name of the table you want to archive the partitions from.
`s3_location` - the location of the data in the partition you want to archive. Note, this should **not** include `s3://` at the beginning, only the bucket name and prefix (s3-bucket/path/to/partition/data/).


## Variables
See below a list of variables that are required, and also some that are optional

|  Variable name           |    example    | description                                                                                     | required |
| ------------------------ | ------------- | ------------------------------------------------------------------------------------------------| -------- |
|    ATHENA_LOG            | s3-athena-log | Location of Athena log files                                                                    |    Y     |
|    CSV_S3_BUCKET         | s3-bucket-csv | S3 bucket that contains the CSV file                                                            |    Y     |
|    CSV_S3_FILE           | file.csv      | Location of the CSV file. Can be a filename, or a prefix + filename (a/path/to/csv.file)        |    Y     |
|    AWS_ACCESS_KEY_ID     | ABCD          | AWS access key ID                                                                               |    Y     |
|    AWS_SECRET_ACCESS_KEY | ABCD1234      | AWS secret access key                                                                           |    Y     |
|    AWS_DEFAULT_REGION    | eu-west-2     | AWS default region                                                                              |    Y     |    

## Example usage
### Running in Docker

Build container
```
docker build -t athena app/
```

Run container
```
docker run -e ATHENA_LOG=s3-athena-log -e AWS_ACCESS_KEY_ID=ABCDEFGHIJLMNOP -e AWS_SECRET_ACCESS_KEY=aBcDe1234+fghijklm01 -e AWS_DEFAULT_REGION=eu-west-2 -e CSV_S3_BUCKET="s3-bucket-containing-csv" -e CSV_S3_FILE="some/prefix/athena-archive-list.csv" athena
```
