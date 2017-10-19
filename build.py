import os
from addict import Dict
from common import log
import time
import io
import tempfile
import subprocess as sub
import boto3
import yaml
# import json

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


def build_albs(full_block, data, config):

    # grab ACM certificates list for later
    cert_list = acm.list_certificates()['CertificateSummaryList']

    # print(data)
    # build alb stack
    counter = Dict()
    for k, v in data.iteritems():
        # print k
        # print v
        counter[v['alb']] += 1
    # print(counter)
    listener_block = {}
    alb_block = {}
    targetgroup_block = {}
    for k, v in counter.iteritems():
        if k:
            # print('key=' + str(k))
            # print('value=' + str(v))

            alb_block.update({
                config['app_name'].upper() + '-ALB-' + k: {
                    "name": config['app_name'].upper() + '-ALB-' + k,
                    "internal": False,
                    "security_groups": config['sg_ids_list'],
                    "subnets": config['subnets_list'],
                    "enable_deletion_protection": True
                }
            })

            targetgroup_block.update({
                config['app_name'].upper() + '-ALB-' + k + '-TG': {
                    "name": config['app_name'].upper() + '-ALB-' + k + '-TG',
                    "port": 80,
                    "protocol": "HTTP",
                    "vpc_id": config['vpc_id'],
                    "enable_deletion_protection": True
                }
            })

            domains_for_this = []
            for d, v in data.iteritems():

                if v['alb'] == k:
                    block = v
                    cert_test_result = filter(lambda cert: cert['DomainName'] == v['domain'], cert_list)
                    cert_arn = cert_test_result[0]['CertificateArn']
                    block['cert_arn'] = cert_arn
                    domains_for_this.append(v)
                # else:
                #     print(v['alb'] + ' is not ' + k)

            # print(json.dumps(domains_for_this, indent=4))

            # Using just the first entry in the filtered domain list because TF requires exactly one
            # Doesn't support the new cert counts right now
            # https://github.com/terraform-providers/terraform-provider-aws/issues/1853
            # so we need to add some logic to add the remaining domains to the listener with boto3.
            # http://boto3.readthedocs.io/en/latest/reference/services/elbv2.html#ElasticLoadBalancingv2.Client.add_listener_certificates
            # it has to happen after terraform runs unfortunately.

            listener_block.update({
                config['app_name'].upper() + '-ALB-' + k + "-LISTENER": {
                    "load_balancer_arn": "${aws_lb." + config['app_name'].upper() + '-ALB-' + v['alb'] + '.arn}',
                    "port": "443",
                    "protocol": "HTTPS",
                    "ssl_policy": config['ssl_policy'],
                    "certificate_arn": domains_for_this[0]['cert_arn'],
                    "default_action": {
                        "target_group_arn": "${aws_lb_target_group." + config['app_name'].upper() + '-ALB-' + v['alb'] + '-TG' + '.arn}',
                        "type": "forward"
                    }
                }
            })

    full_block['resource']['aws_lb'].update(alb_block)
    full_block['resource']['aws_lb_target_group'].update(targetgroup_block)
    full_block['resource']['aws_lb_listener'].update(listener_block)

    return full_block


def build_domains(full_block, data, config):
    # print(json.dumps(data, indent=4))
    # print(json.dumps(acm.list_certificates(), indent=4))
    cert_list = acm.list_certificates()['CertificateSummaryList']
    for k, v in data.iteritems():
        try:
            # print(d)
            # print('alb: ' + d['alb_arn'])
            if not v['alb']:
                # print('found')
                # find and assign an ALB here
                counter = Dict()
                for i in data:
                    counter[v['alb']] += 1
                # counter
                for k, v in counter.iteritems():
                    if v < 20:
                        # data.alb_arn = v
                        # print(v)
                        break
                pass
            else:
                # print(v)
                pass
            # print(v)
            # time.sleep(1)

            # check to see if the cert exists
            # if not then create and grab arn
            # if so then grab arn

            cert_test_result = filter(lambda cert: cert['DomainName'] == v['domain'], cert_list)
            if not cert_test_result:
                print('Create an ACM cert for ' + v['domain'])
                acm_response = acm.request_certificate(DomainName=v['domain'])
                cert_arn = acm_response['CertificateArn']
            else:
                # print(cert_test_result)
                cert_arn = cert_test_result[0]['CertificateArn']

            aws_route53_zone_block = {
                v['domain'].replace('.', '-') + '-' + 'route53zone': {
                    "name": v['domain']
                }
            }

            aws_route53_record_block = {
                v['domain'].replace('.', '-') + '-' + 'route53record-elb': {
                    "zone_id": "${aws_route53_zone." + v['domain'].replace('.', '-') + '-' + 'route53zone' + ".zone_id}",
                    "name": v['domain'],
                    "type": "A",
                    "alias": {
                        "name": "${aws_lb." + config['app_name'].upper() + '-ALB-' + v['alb'] + ".dns_name}",
                        "zone_id": "${aws_lb." + config['app_name'].upper() + '-ALB-' + v['alb'] + ".}",
                        "evaluate_target_health": True
                    }
                }
            }

            full_block['resource']['aws_route53_record'].update(aws_route53_record_block)
            full_block['resource']['aws_route53_zone'].update(aws_route53_zone_block)
        except TypeError:
            pass

    return full_block


def tf_run(full_block, data, config):
    try:
        s3.download_file(config['tfstate_bucket'], config['tfstate_path'] + 'terraform.tfstate', '/tmp/terraform.tfstate')
    except:
        log('Could not find the state file in s3.  Moving on...')
    else:
        starttime = time.time()
        # creds = json.loads(open('creds.json').read())
        env = config.copy()
        env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games' + \
                      env["PATH"]
        # env.update(creds)
        tmpout = tempfile.NamedTemporaryFile().name
        tmperr = tempfile.NamedTemporaryFile().name
        with \
                io.open(tmpout, 'wb') as out_writer, \
                io.open(tmpout, 'rb', 1) as out_reader, \
                io.open(tmperr, 'wb') as err_writer, \
                io.open(tmperr, 'rb', 1) as err_reader:
            pop = sub.Popen('./terraform_' + config['runtime'] + ' apply -refresh=true -state /tmp/terraform.tfstate /tmp/', env=env, stdout=out_writer, stderr=err_writer, shell=True)
            p = ''
            pe = ''
            try:
                while True:
                    for x in range(0, 99):
                        out = out_reader.readline()
                        if out.decode() is not None:
                            log(out.decode(), "info")
                    for x in range(0, 99):
                        err = err_reader.readline()
                        if err.decode() is not None:
                            log(err.decode(), "error")
                    if pop.poll() is not None:
                        break
            except Exception as e:
                log('Error while grabbing output of subprocess. ' + str(e), "error")
        endtime = time.time()
        runtime = float(endtime) - float(starttime)
        os.remove(tmpout)
        os.remove(tmperr)
        log("Ran in [" + str(runtime) + "] seconds...", "info")

        s3.upload_file('/tmp/terraform.tfstate', config['tfstate_bucket'], config['tfstate_path'] + 'terraform.tfstate')
        s3.upload_file('/tmp/infra.tf.json', config['tfstate_bucket'], config['tfstate_path'] + 'infra.tf.json')

        os.remove('/tmp/terraform.tfstate')
        os.remove('/tmp/terraform.tfstate.backup')
