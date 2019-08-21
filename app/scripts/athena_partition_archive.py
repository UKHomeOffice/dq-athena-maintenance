"""
Athena partitioning script
"""


import os
import sys
import time
import random
import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import csv
import json
import re
import urllib.request
import boto3
from dateutil.relativedelta import relativedelta
from botocore.config import Config
from botocore.exceptions import ClientError

ATHENA_LOG = os.environ['ATHENA_LOG']
CSV_S3_BUCKET = os.environ['CSV_S3_BUCKET']
CSV_S3_FILE = os.environ['CSV_S3_FILE']


PATTERN = re.compile("20[0-9]{2}-[0-9]{1,2}-[0-9]{1,2}")
MAXCLEARDOWN = ((datetime.date.today() - relativedelta(months=2)).replace(day=1) - datetime.timedelta(days=1))
LOG_FILE = "/APP/athena-partition.log"

"""
Setup Logging
"""
LOGFORMAT = '%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'
FORM = logging.Formatter(LOGFORMAT)
logging.basicConfig(
    format=LOGFORMAT,
    level=logging.INFO
)
LOGGER = logging.getLogger()
if LOGGER.hasHandlers():
    LOGGER.handlers.clear()
LOGHANDLER = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=7)
LOGHANDLER.suffix = "%Y-%m-%d"
LOGHANDLER.setFormatter(FORM)
LOGGER.addHandler(LOGHANDLER)
CONSOLEHANDLER = logging.StreamHandler()
CONSOLEHANDLER.setFormatter(FORM)
LOGGER.addHandler(CONSOLEHANDLER)
LOGGER.info("Starting")

LOG_GROUP_NAME = None
LOG_STREAM_NAME = None


CONFIG = Config(
    retries=dict(
        max_attempts=10
    )
)

S3 = boto3.client('s3')
ATHENA = boto3.client('athena', config=CONFIG)

def error_handler(lineno, error):
    """
    Error Handler

    Can submit Cloudwatch events if LOG_GROUP_NAME and LOG_STREAM_NAME are set.
    """

    LOGGER.error('The following error has occurred on line: %s', lineno)
    LOGGER.error(str(error))
    sess = boto3.session.Session()
    region = sess.region_name

    raise Exception("https://{0}.console.aws.amazon.com/cloudwatch/home?region={0}#logEventViewer:group={1};stream={2}".format(region, LOG_GROUP_NAME, LOG_STREAM_NAME))

def send_message_to_slack(text):
    """
    Formats the text provides and posts to a specific Slack web app's URL

    Args:
        text : the message to be displayed on the Slack channel

    Returns:
        Slack API repsonse
    """


    try:
        post = {
            "text": ":fire: :sad_parrot: An error has occured in the *Athena Partition Maintenace* pod :sad_parrot: :fire:",
            "attachments": [
                {
                    "text": "{0}".format(text),
                    "color": "#B22222",
                    "attachment_type": "default",
                    "fields": [
                        {
                            "title": "Priority",
                            "value": "High",
                            "short": "false"
                        }
                    ],
                    "footer": "Kubernetes API",
                    "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png"
                }
            ]
            }

        ssm_param_name = 'slack_notification_webhook'
        ssm = boto3.client('ssm', config=CONFIG)
        try:
            response = ssm.get_parameter(Name=ssm_param_name, WithDecryption=True)
        except ClientError as err:
            if err.response['Error']['Code'] == 'ParameterNotFound':
                LOGGER.info('Slack SSM parameter %s not found. No notification sent', ssm_param_name)
                return
            else:
                LOGGER.error("Unexpected error when attempting to get Slack webhook URL: %s", err)
                return
        if 'Value' in response['Parameter']:
            url = response['Parameter']['Value']

            json_data = json.dumps(post)
            req = urllib.request.Request(
                url,
                data=json_data.encode('ascii'),
                headers={'Content-Type': 'application/json'})
            LOGGER.info('Sending notification to Slack')
            response = urllib.request.urlopen(req)

        else:
            LOGGER.info('Value for Slack SSM parameter %s not found. No notification sent', ssm_param_name)
            return

    except Exception as err:
        LOGGER.error(
            'The following error has occurred on line: %s',
            sys.exc_info()[2].tb_lineno)
        LOGGER.error(str(err))

def clear_down(sql):
    """
    After an Athena failure, delete the target path before the sql is retried

    Args:
        sql         : the SQL to execute
    Returns:
        None
    """

    try:
        full_path = sql.split('s3://')[1].split("'")[0]
        bucket_name = full_path.split('/')[0]
        path_to_delete = '/'.join(full_path.split('/')[1:])

        LOGGER.info(
            'Attempting to delete %s from bucket %s',
            path_to_delete,
            bucket_name)

        bucket = S3.Bucket(bucket_name)
        response = bucket.objects.filter(Prefix=path_to_delete).delete()
        LOGGER.info(response)

        if not response:
            LOGGER.info('Nothing to delete')
        else:
            LOGGER.info('The following was deleted: %s', response[0]['Deleted'])

    except Exception as err:
        send_message_to_slack(err)
        error_handler(sys.exc_info()[2].tb_lineno, err)

def check_query_status(execution_id):
    """
    Loop until the query is either successful or fails

    Args:
        execution_id             : the submitted query execution id

    Returns:
        None
    """
    try:
        client = boto3.client('athena', config=CONFIG)
        LOGGER.debug('About to check Athena status on SQL')
        while True:
            response = client.get_query_execution(
                QueryExecutionId=execution_id)
            if response['QueryExecution']['Status']['State'] in ('FAILED', 'SUCCEEDED', 'CANCELLED'):
                return response
            LOGGER.debug('Sleeping for 1 second')
            time.sleep(1)

    except Exception as err:
        send_message_to_slack(err)
        error_handler(sys.exc_info()[2].tb_lineno, err)

def execute_athena(sql, database_name):
    """
    Run SQL on Athena.

    Args:
        sql             : the SQL to execute
        conditions      : dict of optional pre and post execution conditions
        output_location : the S3 location for Athena to put the results

    Returns:
        response        : response of submitted Athena query
    """


    try:
        attempts = 8
        i = 1
        while True:
            if i == attempts:
                LOGGER.error('%s attempts made. Failing with error', attempts)
                sys.exit(1)
            try:
                response = ATHENA.start_query_execution(
                    QueryString=sql,
                    QueryExecutionContext={
                        'Database': database_name
                        },
                    ResultConfiguration={
                        'OutputLocation': "s3://" + ATHENA_LOG,
                        }
                    )
            except ClientError as err:
                if err.response['Error']['Code'] in (
                        'TooManyRequestsException',
                        'ThrottlingException',
                        'SlowDown'):
                    LOGGER.info('athena.start_query_execution throttled. Waiting %s second(s) before trying again', 2 ** i)
                    time.sleep((2 ** i) + random.random())
                else:
                    raise err
                i += 1
            else:
                LOGGER.debug('Athena query submitted. Continuing.')
                LOGGER.debug(response)
                response = check_query_status(response['QueryExecutionId'])
                if response['QueryExecution']['Status']['State'] == 'CANCELLED':
                    LOGGER.warning(response)
                    LOGGER.debug('SQL query cancelled. Waiting %s second(s) before trying again', 2 ** i)
                    time.sleep((2 ** i) + random.random())
                    i += 1
                    clear_down(sql)
                if response['QueryExecution']['Status']['State'] == 'FAILED':
                    LOGGER.warning(response)
                    state_change_reason = response['QueryExecution']['Status']['StateChangeReason']
                    compiled = re.compile("Table*does not exist")
                    compiled_not_found = re.compile("Table not found*")
                    if "Query exhausted resources at this scale factor" in state_change_reason \
                       or "Partition metadata not available" in state_change_reason \
                       or "INTERNAL_ERROR" in state_change_reason \
                       or "ABANDONED_QUERY" in state_change_reason \
                       or "HIVE_PATH_ALREADY_EXISTS" in state_change_reason \
                       or "HIVE_CANNOT_OPEN_SPLIT" in state_change_reason \
                       or compiled.match(state_change_reason) \
                       or compiled_not_found.match(state_change_reason):
                        LOGGER.debug('SQL query failed. Waiting %s second(s) before trying again', 2 ** i)
                        time.sleep((2 ** i) + random.random())
                        i += 1
                        clear_down(sql)
                    if "Table not found" in state_change_reason:
                        LOGGER.warning('Database / Table not found, continuing.')
                        LOGGER.warning(sql)
                        send_message_to_slack('Database / Table not found')
                        sys.exit(1)
                    else:
                        send_message_to_slack('SQL query failed and this type of error will not be retried. Exiting with failure.')
                        LOGGER.error('SQL query failed and this type of error will not be retried. Exiting with failure.')
                        sys.exit(1)
                elif response['QueryExecution']['Status']['State'] == 'SUCCEEDED':
                    LOGGER.debug('SQL statement completed successfully')
                    break

    except Exception as err:
        send_message_to_slack(err)
        error_handler(sys.exc_info()[2].tb_lineno, err)

    return response

def main():
    """
    Main function to execute Athena queries
    """

    attempts = 4
    i = 1
    try:
        while True:
            if i == attempts:
                LOGGER.error('%s attempts made. Failing with error', attempts)
                sys.exit(1)
            try:
                S3.download_file(CSV_S3_BUCKET, CSV_S3_FILE, "/APP/list.csv")
            except ClientError as err:
                error_code = err.response['Error']['Code']
                if error_code == "404":
                    err = "Parition list not found in S3: " + CSV_S3_BUCKET + "/" + CSV_S3_FILE
                    LOGGER.error(err)
                    send_message_to_slack(err)
                    sys.exit(1)
                else:
                    raise err
                i += 1
            else:
                LOGGER.info('Successfully pulled CSV')
                break
    except Exception as err:
        send_message_to_slack(err)
        error_handler(sys.exc_info()[2].tb_lineno, err)

    try:
        with open("/APP/list.csv") as csv_file:
            csv_reader = csv.DictReader(csv_file)

            for row in csv_reader:
                database_name = row["database_name"]
                table_name = row["table_name"]
                s3_location = row["s3_location"]

                LOGGER.info('Processing %s.%s', database_name, table_name)

                sql = "show partitions " + database_name + "." + table_name

                response = execute_athena(sql, database_name)
                query_file = response['QueryExecution']['QueryExecutionId'] + '.txt'

                # Sleep to allow file to be written to S3
                time.sleep(1)

                S3.download_file(ATHENA_LOG, query_file, "/APP/query.txt")

                result_list = []

                with open("/APP/query.txt") as file:
                    for line in file:
                        line = line.strip()
                        result_list.append(line)

                partition_list = []

                for item in result_list:
                    try:
                        match = PATTERN.search(item).group(0)
                    except:
                        LOGGER.info("No match found.")
                    if match <= str(MAXCLEARDOWN):
                        partition_list.append(item)

                for item in partition_list:
                    item_quoted = item[:10] + "'" + item[10:] + "'"
                    item_stripped = item.split('=')[1]

                    drop_partition_sql = ("ALTER TABLE " + database_name + "." + table_name + \
                                         " DROP PARTITION (" + item_quoted + ");")
                    add_partition_sql = ("ALTER TABLE " + database_name + "." + table_name + \
                                         "_archive ADD PARTITION (" + item_quoted + ") LOCATION 's3://" + s3_location + "/" + item_stripped + "';")


                    try:
                        LOGGER.info('Dropping partition "%s" from "%s.%s"', item, database_name, table_name)
                        LOGGER.debug(drop_partition_sql)
                        execute_athena(drop_partition_sql, database_name)
                    except Exception as err:
                        send_message_to_slack(err)
                        error_handler(sys.exc_info()[2].tb_lineno, err)
                        sys.exit(1)

                    try:
                        LOGGER.info('Adding partition "%s" from "%s.%s"', item, database_name, table_name)
                        LOGGER.debug(add_partition_sql)
                        execute_athena(add_partition_sql, database_name)
                    except Exception as err:
                        send_message_to_slack(err)
                        error_handler(sys.exc_info()[2].tb_lineno, err)
                        sys.exit(1)

                LOGGER.info("Complete.")

        LOGGER.info("Were done here.")
    except Exception as err:
        send_message_to_slack(err)
        error_handler(sys.exc_info()[2].tb_lineno, err)


if __name__ == '__main__':
    main()
