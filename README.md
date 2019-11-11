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

|  database_name  |  table_name  |             s3_location             |  retention_period  | days_to_keep | partitioned_by |
| --------------- | ------------ | ----------------------------------- | ------------------ | ------------ | -------------- |
|    database1    |    table1    | s3-bucket/path/to/partition/data/   | 2MonthsPlusCurrent |              |                |
|    database1    |    table2    | s3-bucket/path/to/partition/data/   | 2MonthsPlusCurrent |              |                |
|    database1    |    table3    | s3-bucket/path/to/partition/data/   | 2MonthsPlusCurrent |              |                |
|    database2    |    table1    | s3-bucket/path/to/partition/data/   | 30Days             |              |                |
|    database3    |    table1    | s3-bucket/path/to/partition/data/   | PartitionMaxDate   | 30           | date_local     |

* `database_name`    - the name of the database (schema).
* `table_name`       - the name of the table you want to archive the partitions from.
* `s3_location`      - the location of the data in the partition you want to archive. Note, this should **not** include  `s3://` at the beginning, only the bucket name and prefix (s3-bucket/path/to/partition/data/).
* `retention_period` - the method of partitioning (explained below).
* `days_to_keep`     - the number of days to keep (**not** required unless using PartitionMaxDate).
* `partitioned_by`   - the column that MAX should be taken from (**not** required unless using PartitionMaxDate).

## Partition retention options
`retention_period` set in the CSV can contain one of 3 options:-

* `2MonthsPlusCurrent` - Removes any partitions where the path_name is older than 2 months plus the current month.
* `30Days`             - Removes any partitions where the path_name is older than 2 months plus the current month.
* `PartitionMaxDate`   - Removes partitions where the MAX value of the column set in `partitioned_by` is older than the number of days set in `days_to_keep`.


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

## Useful commands
Run a one time instance of the job:-
```
kubectl create job dq-athena-partition-maintenance --from=cronjob/dq-athena-partition-maintenance
```

There is a branch titled no-date-comparison which is a long-live branch. This branch has changes to the script whereby it:-
* will run regardless of the date - the main script only runs some of the partition maintenance on the 1st of the month
* Silences slack alerts
* Ignores partitions that already exist.

To deploy this branch:-

`drone deploy UKHomeOffice/dq-athena-maintenance 102 production`

`kubectl delete jobs dq-athena-partition-maintenance-one-off && kubectl create job dq-athena-partition-maintenance-one-off --from=cronjob/dq-athena-partition-maintenance && sleep 5 && kgp | grep dq-athena-partition-maintenance-one-off`

This should start the job running. Use `kubectl logs -f dq-athena-partition-maintenance-one-off<pod_id>` to tail the logs.
Once it has finished:-

`kubectl delete jobs dq-athena-partition-maintenance-one-off`

`drone deploy UKHomeOffice/dq-athena-maintenance X production` - where X is the latest production build.
