#!/usr/bin/python

import json
import boto3
from common import log
# from db_mysql import get_data_mysql
from build import build_albs, build_domains, tf_run
import yaml

s3 = boto3.client('s3')
s3res = boto3.resource('s3')

config = yaml.load(open('config.yml'))


def handler(event, context):

    # Connect to a mysql database to pull data instead of json file
    # data = get_data_mysql(os.environ['db_host'], os.environ['db_user'], os.environ['db_password'], os.environ['db_schema'], os.environ['db_table'])

    # or get data from json
    with open('testdata/data.json') as data_file:
        data = json.load(data_file)
        # print(data)

    # print(json.dumps(config, indent=4))

    # log(json.dumps(thread_jobs, indent=4, sort_keys=False))

    # init the full block with basic structure
    full_block = {
        "provider": {
            "aws": {
                "region": config['aws_region']
            }
        },
        "resource": {
            "aws_lb": {},
            "aws_lb_listener": {},
            "aws_lb_target_group": {},
            "aws_lb_target_group_attachment": {},
            "aws_route53_record": {},
            "aws_route53_zone": {}
        }
    }

    # build alb stack
    full_block = build_albs(full_block, data, config)

    # build listeners
    full_block = build_domains(full_block, data, config)

    # construct the terraform infra file
    terraform_config = open('infra.tf.json', 'w')
    terraform_config.write(json.dumps(full_block, indent=4, sort_keys=False))
    terraform_config.close()

    # run the terraform
    # dont do this yet until you validate the new ACM SSL certificates through emails.  See the readme for more information.
    # tf_run(full_block, data, config)


handler(1, 2)

