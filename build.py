import os
from addict import Dict
from common import log
import time
import io
import tempfile
import subprocess as sub
import boto3
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


def build_albs(full_block, data, config):
    # print(data)
    # build alb stack
    counter = Dict()
    for k, v in data.iteritems():
        # print k
        # print v
        counter[v['alb']] += 1
    # print(counter)
    for k, v in counter.iteritems():
        if k:
            # print('key=' + str(k))
            # print('value=' + str(v))

            alb_block = {
                config['app_name'].upper() + '-ALB-' + k: {
                    "name": config['app_name'].upper() + '-ALB-' + k,
                    "internal": False,
                    "security_groups": config['sg_ids_list'],
                    "subnets": config['subnets_list'],
                    "enable_deletion_protection": True
                }
            }

            targetgroup_block = {
                config['app_name'].upper() + '-ALB-' + k + '-TG': {
                    "name": config['app_name'].upper() + '-ALB-' + k + '-TG',
                    "port": 80,
                    "protocol": "HTTP",
                    "vpc_id": config['vpc_id'],
                    "enable_deletion_protection": True
                }
            }

            # targetgroupassignment_block = {
            #     config['app_name'].upper() + '-ALB-' + k + '-TG-assignment': {
            #         "target_group_arn": "${aws_lb_target_group." + config['app_name'].upper() + '-ALB-' + k + '-TG' + '.arn}',
            #         "target_id": config['asg_id']
            #     }
            # }

            full_block['resource']['aws_lb'].update(alb_block)
            full_block['resource']['aws_lb_target_group'].update(targetgroup_block)
            # full_block['resource']['aws_lb_target_group_attachment'].update(targetgroupassignment_block)

    return full_block


def build_listeners(full_block, data, config):
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
            # print(acm.list_certificates())
            cert_test_result = filter(lambda cert: cert['DomainName'] == v['domain'], cert_list)
            if not cert_test_result:
                print('Create an ACM cert for ' + v['domain'])
                acm_response = acm.request_certificate(DomainName=v['domain'])
                # print(json.dumps(acm_response, indent=4))
                cert_arn = acm_response['CertificateArn']
            else:
                print(cert_test_result)
                cert_arn = cert_test_result[0]['CertificateArn']

            listener_block = {
                v['domain'].replace('.', '-') + '-' + 'listener': {
                    "load_balancer_arn": "${aws_lb." + config['app_name'].upper() + '-ALB-' + v['alb'] + '.arn}',
                    "port": "443",
                    "protocol": "HTTPS",
                    "ssl_policy": config['ssl_policy'],
                    "certificate_arn": cert_arn,
                    "default_action": {
                        "target_group_arn": "${aws_lb_target_group." + config['app_name'].upper() + '-ALB-' + v['alb'] + '-TG' + '.arn}',
                        "type": "forward"
                    }
                }
            }

            full_block['resource']['aws_lb_listener'].update(listener_block)
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
