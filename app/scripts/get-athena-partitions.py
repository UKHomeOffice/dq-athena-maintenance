"""
Athena partitioning script
"""

import boto3
import os
import sys
import time
import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import re
from dateutil.relativedelta import relativedelta
from datetime import date
from botocore.config import Config


"""
Define variables
"""
athena_log = os.environ['athena_log']
s3_prefix = os.environ['s3_prefix']
database_name = os.environ['database_name']
table_name = os.environ['table_name']
s3_location = os.environ['s3_location']

query = "show partitions " + database_name + "." + table_name
pattern = re.compile("20[0-9]{2}-[0-9]{1,2}-[0-9]{1,2}")
maxcleardown = ((datetime.date.today() - relativedelta(months=2)).replace(day=1) - datetime.timedelta(days=1))
mincleardown = (maxcleardown - datetime.timedelta(days=31))
log_file = "/APP/athena-partition.log"

"""
Setup Logging
"""
logformat = '%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'
form = logging.Formatter(logformat)
logging.basicConfig(
    format=logformat,
    level=logging.INFO
)
LOGGER = logging.getLogger()
if LOGGER.hasHandlers():
    LOGGER.handlers.clear()
loghandler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7)
loghandler.suffix = "%Y-%m-%d"
loghandler.setFormatter(form)
LOGGER.addHandler(loghandler)
consolehandler = logging.StreamHandler()
consolehandler.setFormatter(form)
LOGGER.addHandler(consolehandler)
LOGGER.info("Starting")

LOG_GROUP_NAME = None
LOG_STREAM_NAME = None


CONFIG = Config(
    retries=dict(
        max_attempts=10
    )
)

s3 = boto3.client('s3')
athena = boto3.client('athena', config=CONFIG)

def error_handler(lineno, error):

    LOGGER.error('The following error has occurred on line: %s', lineno)
    LOGGER.error(str(error))
    sess = boto3.session.Session()
    region = sess.region_name

    raise Exception("https://{0}.console.aws.amazon.com/cloudwatch/home?region={0}#logEventViewer:group={1};stream={2}".format(region, LOG_GROUP_NAME, LOG_STREAM_NAME))


def main():

    # ADD Check if archive table exists
    query_response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            'Database': database_name
            },
        ResultConfiguration={
            'OutputLocation': "s3://" + athena_log + "/" + s3_prefix,
            }
        )
    query_file = query_response['QueryExecutionId'] + '.txt'

    time.sleep(1)
    s3_object = s3.get_object(Bucket=athena_log, Key=(s3_prefix + query_file))
    body = s3_object['Body']

    for obj in body:
        result = obj.decode('utf-8')
        list = result.split()

    partition_list = []

    for item in list:
        match = pattern.search(item).group(0)

        if match <= str(maxcleardown):
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

            query_response = athena.start_query_execution(
                QueryString=drop_partition_sql,
                QueryExecutionContext={
                    'Database': database_name
                    },
                ResultConfiguration={
                    'OutputLocation': "s3://" + athena_log + "/" + s3_prefix,
                    }
                )
        except Exception as err:
            LOGGER.error(
                'The following error has occurred on line: %s',

                sys.exc_info()[2].tb_lineno)
            LOGGER.error(str(err))
            sys.exit(1)

        try:
            LOGGER.info('Adding partition "%s" from "%s.%s"', item, database_name, table_name)

            query_response = athena.start_query_execution(
                QueryString=add_partition_sql,
                QueryExecutionContext={
                    'Database': database_name
                    },
                ResultConfiguration={
                    'OutputLocation': "s3://" + athena_log + "/" + s3_prefix,
                    }
                )
        except Exception as err:
            LOGGER.error(
                'The following error has occurred on line: %s',

                sys.exc_info()[2].tb_lineno)
            LOGGER.error(str(err))
            sys.exit(1)
    LOGGER.info("Were done here.")

if __name__ == '__main__':
    main()
