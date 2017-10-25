#!/usr/bin/python

import json
import boto3
from common import log
# from db_mysql import get_data_mysql
from build import build_albs, build_domains, build_certs, tf_run
import yaml

config = yaml.load(open('config.yml'))

try:
    if config['aws_profile']:
        session = boto3.Session(profile_name=config['aws_profile'], region_name=config['aws_region'])
except KeyError:
    session = boto3.Session(region_name=config['aws_region'])

s3 = session.client('s3')
s3res = session.resource('s3')
acm = session.client('acm')
elb = session.client('elbv2')


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

    cert_info = build_certs(full_block, data, config)

    # build alb stack
    full_block = build_albs(full_block, data, config, cert_info)

    # build listeners
    full_block = build_domains(full_block, data, config, cert_info)

    # construct the terraform infra file
    terraform_config = open('infra.tf.json', 'w')
    terraform_config.write(json.dumps(full_block, indent=4, sort_keys=False))
    terraform_config.close()

    # run the terraform
    # dont do this yet until you validate the new ACM SSL certificates through emails.  See the readme for more information.
    # tf_run(full_block, data, config)

    cert_list = acm.list_certificates()['CertificateSummaryList']
    print(json.dumps(cert_list, indent=4))
    certs_to_add = []
    for k, v in cert_info['alb_groups'].iteritems():
        print('TO ADD TO ' + str(k))
        # print(json.dumps(v, indent=4))
        for cert in v[config['max_doms']::config['max_doms']]:
            # print(cert)
            cert_data = filter(lambda cert1: cert1['DomainName'] == cert, cert_list)
            try:
                arn_to_add = cert_data[0]['CertificateArn']
            except IndexError:
                pass
            else:
                print(arn_to_add)
                # TODO: get alb arn
                # TODO: add cert to


handler(1, 2)

