# dq-athena-maintenance

## Introduction
This app archive's tables in Athena and is designed to run in Kubernetes.

It currently only supports a rule to archive data that is older than 2 months + current.

A CSV file must exist in S3 which contains the database name, table name and S3 location of the data.

## CSV file
The CSV file must **not** be in utf-8.

The layout of the CSV file is as follows:-

|  database_name  |  table_name  |      s3_location      |
| --------------- | ------------ | --------------------- |
|    database1    |    table1    | s3-a-location/in/s3   |
|    database1    |    table2    | s3-a-location/in/s3   |
|    database1    |    table3    | s3-a-location/in/s3   |
|    database2    |    table1    | s3-a-location/in/s3   |
|    database3    |    table1    | s3-a-location/in/s3   |


## Variables
See below a list of variables that are required, and also some that are optional

|  Variable name   |    example            | description                                                                                     | required |
| ------------------------ | ------------  | ------------------------------------------------------------------------------------------------| -------- |
|    ATHENA_LOG            | s3-athena-log | Location of Athena log files                                                                    |    Y     |
|    CSV_S3_BUCKET         | s3-bucket-csv | S3 bucket that contains the CSV file                                                            |    Y     |
|    CSV_S3_FILE           | file.csv      | Location of the CSV file. Can be a filename, or a prefix + filename (a/path/to/csv.file)        |    Y     |
|    AWS_ACCESS_KEY_ID     | ABCD          | AWS access key ID                                                                               |    Y     |
|    AWS_SECRET_ACCESS_KEY | ABCD1234      | AWS secret access key                                                                           |    Y     |
