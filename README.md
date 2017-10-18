## DNS-MANAGER
###### A buildout tool for large numbers on domainname/alb relationships


#### Abstract

> This is a tool that is designed to take input from a database or json file that defines a list of domains and which ALB they should be assigned to.  Works by doing the following:
> * Grabs the domains and info
> * Creates/maintains enough ALBs to support the domains
> * Creates ACM certificate for each domain
> * Creates a Route53 hosted zone and record set for each domain and attaches the cert and the ALB listener it should be assigned to based on its database entry.


#### Environment Variables

> This tool relies on a set of variables outlined in config.yml.  Ensure that you replace the dummy values with correct ids and values.


#### Dependencies

> * This tool relies on a few specific dependencies
>   * terraform binaries
>     * the latest (v0.10.7) version is supplied, but to use a newer version just download the newer binary from https://www.terraform.io/downloads.html
>   * PyMySQL
>     * if you need to use a MySQL connector to get the domain data, you need PyMySQL, but you could also write whatever connector you need.
>   * Addict
>     * this is a nifty little python package that I use to count some datas
>   * Boto3
>     * obvious, but yes we need this to create the ACM certificates.

#### Limitations

> At the moment, we are dealing with the following limitations.  I'll knock these down as we go along with development, but if you have any suggestions feel free to submit a PR.
> * Certificate Validation
>   * We are using ACM to generate certificates, and ACM uses email to verify ownership.  So we need to figure out a way to automatically click through the emails that come in if we are going to do this at large scale.
>   * because of this, you would need to validate the ACM certs BEFORE you run the generated infra.tf.json or Terraform will fail as the certs need to be validated before they can be added to any resources.
> * AutoScaling Group Automation
>   * At this point, after the TF creates the certs, ALBs, and targetgroups, you will need to then add the target groups manually to whichever ASG this traffic should point to.
>   * to automate this, we probably just need to add a few commands to edit the ASG to connect the target groups that are created, but this can be risky if the ASG is handled through a separate infrastructure-as-code solution as it the case with Rackspace Aviator.  Need to put in a little more thought to make this elegant.
> * Because Terraform doesn't support the new "multiple-ssl" features in ALB listeners yet, we need to add the listeners after terraform executes.
>   * http://boto3.readthedocs.io/en/latest/reference/services/elbv2.html#ElasticLoadBalancingv2.Client.add_listener_certificates
>   * https://github.com/terraform-providers/terraform-provider-aws/issues/1853