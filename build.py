import os
from addict import Dict
from common import log
import time
import io
import tempfile
import subprocess as sub
import boto3
import yaml
import json

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


def build_albs(full_block, data, config, cert_info):
    # grab ACM certificates list for later
    cert_list = acm.list_certificates()['CertificateSummaryList']

    # print(data)
    # build alb stack
    counter = Dict()
    for k in data:
        # print k
        # print v
        counter[k['alb']] += 1
    # print(counter)
    listener_block = {}
    alb_block = {}
    targetgroup_block = {}
    for k, v in counter.iteritems():
        if k:
            # print('key=' + str(k))
            # print('value=' + str(v))

            alb_block.update({
                config['app_name'].upper() + '-ALB-' + str(k): {
                    "name": config['app_name'].upper() + '-ALB-' + str(k),
                    "internal": False,
                    "security_groups": config['sg_ids_list'],
                    "subnets": config['subnets_list'],
                    "enable_deletion_protection": True
                }
            })

            targetgroup_block.update({
                config['app_name'].upper() + '-ALB-' + str(k) + '-TG': {
                    "name": config['app_name'].upper() + '-ALB-' + str(k) + '-TG',
                    "port": 80,
                    "protocol": "HTTP",
                    "vpc_id": config['vpc_id'],
                    "enable_deletion_protection": True
                }
            })

            ###################
            # Using just the first entry in the filtered domain list because TF requires exactly one
            # Doesn't support the new cert counts right now
            # https://github.com/terraform-providers/terraform-provider-aws/issues/1853
            # so we need to add some logic to add the remaining domains to the listener with boto3.
            # http://boto3.readthedocs.io/en/latest/reference/services/elbv2.html#ElasticLoadBalancingv2.Client.add_listener_certificates
            # it has to happen after terraform runs unfortunately.
            ###################

            # print(v)

            primary = cert_info['alb_groups'][k][0]

            cert_test_result = filter(lambda cert: cert['DomainName'] == primary, cert_list)
            try:
                primary_cert_arn = cert_test_result[0]['CertificateArn']
            except:
                raise

            # for i in cert_info['alb_groups'][k]:
            #     print(i)

            listener_block.update({
                config['app_name'].upper() + '-ALB-' + str(k) + "-LISTENER": {
                    "load_balancer_arn": "${aws_lb." + config['app_name'].upper() + '-ALB-' + str(k) + '.arn}',
                    "port": "443",
                    "protocol": "HTTPS",
                    "ssl_policy": config['ssl_policy'],
                    "certificate_arn": primary_cert_arn,
                    "default_action": {
                        "target_group_arn": "${aws_lb_target_group." + config['app_name'].upper() + '-ALB-' + str(k) + '-TG' + '.arn}',
                        "type": "forward"
                    }
                }
            })

    full_block['resource']['aws_lb'].update(alb_block)
    full_block['resource']['aws_lb_target_group'].update(targetgroup_block)
    full_block['resource']['aws_lb_listener'].update(listener_block)

    return full_block


def build_domains(full_block, data, config, cert_info):
    for v in data:
        # we need to
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

            aws_route53_zone_block = {
                v['domain'].replace('.', '-') + '-' + 'route53zone': {
                    "name": v['domain']
                }
            }

            aws_route53_record_block = {
                v['domain'].replace('.', '-') + '-' + 'route53record-elb': {
                    "zone_id": "${aws_route53_zone." + v['domain'].replace('.',
                                                                           '-') + '-' + 'route53zone' + ".zone_id}",
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


def build_certs(full_block, data, config):
    # we need to build the certificates first so we can group them appropriately.

    doms_per_cert = config['max_doms']

    certed_domains = []
    cert_list = acm.list_certificates()['CertificateSummaryList']
    # print(json.dumps(cert_list, indent=4))
    # print(len(cert_list))
    for c in cert_list:
        domains_in_this_cert = []
        cert_desc = acm.describe_certificate(CertificateArn=c['CertificateArn'])
        # print(json.dumps(str(cert_desc), indent=4))
        domains_in_this_cert.append(cert_desc['Certificate']['DomainName'])
        # print(cert_desc['Certificate']['DomainName'])
        for domain in cert_desc['Certificate']['SubjectAlternativeNames']:
            # print(domain)
            # print(json.dumps(cert_desc['Certificate']['SubjectAlternativeNames'], indent=4))
            domains_in_this_cert.append(domain)
        # print('*** Cert for ' + cert_desc['Certificate']['DomainName'] + ' is ' + cert_desc['Certificate']['Status'])
        certed_domains += domains_in_this_cert

    # fast dedupe
    def f7(list):
        seen = set()
        seen_add = seen.add
        return [x for x in list if not (x in seen or seen_add(x))]

    certed_domains = f7(certed_domains)

    # if you want to print the certed_domains for troubleshooting
    # print(json.dumps(certed_domains, indent=4))

    # divide domains per into certable chunks
    # ACM only supports 10 domains per cert by default but you can add more

    alb_groups = {}
    for e in data:
        try:
            alb_groups[e['alb']].append(e['domain'])
        except KeyError:
            alb_groups[e['alb']] = []
            alb_groups[e['alb']].append(e['domain'])

    for alb in alb_groups.keys():
        if len(alb_groups[alb]) > int(doms_per_cert) * 25:
            print('You have too many certificates assigned to alb named ' + alb +
                  '.  Skipping cert assignment for this domain until this is corrected.')
            alb_groups.pop(alb, None)

    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in xrange(0, len(l), n):
            yield l[i:i + n]

    # print(json.dumps(alb_groups, indent=4))

    certs_to_build = {}

    for k, v in alb_groups.iteritems():
        # print('FOR ' + str(k))
        for e in list(chunks(v, doms_per_cert)):
            for d in e:
                # print(d)
                if d not in certed_domains:
                    if e[0] not in certs_to_build:
                        try:
                            certs_to_build[k][e[0]] = []
                        except KeyError:
                            certs_to_build[k] = {}
                            certs_to_build[k][e[0]] = []
                    for i in e[1::]:
                        if str(i) not in certed_domains:
                            if i not in certs_to_build[k][e[0]]:
                                # print('trying to put ' + i + ' under ' + e[0])
                                certs_to_build[k][e[0]].append(i)

    # print(json.dumps(certs_to_build, indent=4))

    built_certs = {}
    for alb, certs in certs_to_build.iteritems():
        try:
            if not built_certs[alb]:
                built_certs[alb] = {}
        except KeyError:
            built_certs[alb] = {}
        # print(alb)
        # print(json.dumps(certs, indent=4))
        for master, subs in certs.iteritems():
            # print(cert)
            cert_test_result = filter(lambda cert: cert['DomainName'] == master, cert_list)
            if not cert_test_result:
                print('Create an ACM cert for ' + master)
                if subs:
                    acm_response = acm.request_certificate(DomainName=master, SubjectAlternativeNames=subs)
                else:
                    acm_response = acm.request_certificate(DomainName=master)
                cert_arn = acm_response['CertificateArn']
            else:
                # print(cert_test_result)
                cert_arn = cert_test_result[0]['CertificateArn']
            try:
                built_certs[alb][master]['arn'] = cert_arn
                built_certs[alb][master]['sub_names'] = subs
            except KeyError:
                built_certs[alb][master] = {}
            finally:
                built_certs[alb][master]['arn'] = cert_arn
                built_certs[alb][master]['sub_names'] = subs

    post_cert_list = acm.list_certificates()['CertificateSummaryList']

    # print(json.dumps(built_certs, indent=4))
    # print(json.dumps(cert_list, indent=4))
    cert_info = {
        'built_certs': built_certs,
        'alb_groups': alb_groups,
        'post_cert_list': post_cert_list
    }

    return cert_info


def tf_run(full_block, data, config):
    try:
        s3.download_file(config['tfstate_bucket'], config['tfstate_path'] + 'terraform.tfstate',
                         '/tmp/terraform.tfstate')
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
            pop = sub.Popen(
                './terraform_' + config['runtime'] + ' apply -refresh=true -state /tmp/terraform.tfstate /tmp/',
                env=env, stdout=out_writer, stderr=err_writer, shell=True)
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
