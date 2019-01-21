# Converted from ELBSample.template located at:
# http://aws.amazon.com/cloudformation/aws-cloudformation-templates/

from troposphere import Base64, FindInMap, GetAtt, Join, Output
from troposphere import Parameter, Ref, Template
import troposphere.ec2 as ec2
import troposphere.elasticloadbalancingv2 as elb


def AddAMI(template):
    template.add_mapping("RegionMap", {
        "us-east-1": {"AMI": "ami-009d6802948d06e52"},
        "us-west-1": {"AMI": "ami-011b6930a81cd6aaf"},
        "us-west-2": {"AMI": "ami-011b6930a81cd6aaf"},
        "eu-central-1": {"AMI": "ami-034fffcc6a0063961"},
        "sa-east-1": {"AMI": "ami-0112d42866980b373"}
    })


def main():
    template = Template()
    template.add_version("2010-09-09")

    template.add_description(
        "AWS CloudFormation Sample Template: ELB with 2 EC2 instances")

    AddAMI(template)

    # Add the Parameters
    keyname_param = template.add_parameter(Parameter(
        "KeyName",
        Type='AWS::EC2::KeyPair::KeyName',
        Default="ansible-key",
        Description="Name of an existing EC2 KeyPair to "
                    "enable SSH access to the instance",
    ))

    template.add_parameter(Parameter(
        "InstanceType",
        Type="String",
        Description="WebServer EC2 instance type",
        Default="t2.micro",
        AllowedValues=[
            "t1.micro", "t2.micro"
        ],
        ConstraintDescription="must be a valid EC2 instance type.",
    ))

    webport_param = template.add_parameter(Parameter(
        "WebServerPort",
        Type="String",
        Default="8888",
        Description="TCP/IP port of the web server",
    ))

    web2_param = template.add_parameter(Parameter(
        "ApiServerPort",
        Type="String",
        Default="8889",
        Description="TCP/IP port of the api server",
    ))

    subnetA = template.add_parameter(Parameter(
        "subnetA",
        Type="List<AWS::EC2::Subnet::Id>",
        Description="Choose Subnets"
    ))

    VpcId = template.add_parameter(Parameter(
        "VpcId",
        Type="AWS::EC2::VPC::Id",
        Description="Choose VPC"
    ))

    # Define the instance security group
    instance_sg = template.add_resource(
        ec2.SecurityGroup(
            "InstanceSecurityGroup",
            GroupDescription="Enable SSH and HTTP access on the inbound port",
            SecurityGroupIngress=[
                ec2.SecurityGroupRule(
                    IpProtocol="tcp",
                    FromPort="22",
                    ToPort="22",
                    CidrIp="0.0.0.0/0",
                ),
                ec2.SecurityGroupRule(
                    IpProtocol="tcp",
                    FromPort=Ref(webport_param),
                    ToPort=Ref(webport_param),
                    CidrIp="0.0.0.0/0",
                ),
                ec2.SecurityGroupRule(
                    IpProtocol="tcp",
                    FromPort=Ref(web2_param),
                    ToPort=Ref(web2_param),
                    CidrIp="0.0.0.0/0",
                ),
            ]
        )
    )

    # Add the web server instance
    WebInstance = template.add_resource(ec2.Instance(
        "WebInstance",
        SecurityGroups=[Ref(instance_sg)],
        KeyName=Ref(keyname_param),
        InstanceType=Ref("InstanceType"),
        ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
        UserData=Base64(Join('',[
            '#!/bin/bash\n',
            'sudo yum -y update\n',
            'sudo yum install -y httpd php\n',
            'sudo sed - i "42s/Listen 80/Listen 8888/" / etc / httpd / conf / httpd.conf\n',
            'sudo service httpd restart \n',
            'Ref(webport_param)',
    ]))))

    # Add the api server instance
    ApiInstance = template.add_resource(ec2.Instance(
        "ApiInstance",
        SecurityGroups=[Ref(instance_sg)],
        KeyName=Ref(keyname_param),
        InstanceType=Ref("InstanceType"),
        ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
    UserData = Base64(Join('', [
        '#!/bin/bash\n',
        'sudo yum -y update\n',
        'sudo yum install -y httpd php\n',
        'sudo sed - i "42s/Listen 80/Listen 8889/" / etc / httpd / conf / httpd.conf\n',
        'sudo service httpd restart \n',
        'Ref(web2_param)',
    ]))))

    # Add the application ELB
    ApplicationElasticLB = template.add_resource(elb.LoadBalancer(
        "ApplicationElasticLB",
        Name="ApplicationElasticLB",
        Scheme="internet-facing",
        Subnets=Ref("subnetA")
    ))

    TargetGroupWeb = template.add_resource(elb.TargetGroup(
        "TargetGroupWeb",
        HealthCheckIntervalSeconds="30",
        HealthCheckProtocol="HTTP",
        HealthCheckTimeoutSeconds="10",
        HealthyThresholdCount="4",
        Matcher=elb.Matcher(
            HttpCode="200"),
        Name="WebTarget",
        Port=Ref(webport_param),
        Protocol="HTTP",
        Targets=[elb.TargetDescription(
            Id=Ref(WebInstance),
            Port=Ref(webport_param))],
        UnhealthyThresholdCount="3",
        VpcId=Ref(VpcId)

    ))

    TargetGroupApi = template.add_resource(elb.TargetGroup(
        "TargetGroupApi",
        HealthCheckIntervalSeconds="30",
        HealthCheckProtocol="HTTP",
        HealthCheckTimeoutSeconds="10",
        HealthyThresholdCount="4",
        Matcher=elb.Matcher(
            HttpCode="200"),
        Name="ApiTarget",
        Port=Ref(web2_param),
        Protocol="HTTP",
        Targets=[elb.TargetDescription(
            Id=Ref(ApiInstance),
            Port=Ref(web2_param))],
        UnhealthyThresholdCount="3",
        VpcId=Ref(VpcId)

    ))

    Listener = template.add_resource(elb.Listener(
        "Listener",
        Port="80",
        Protocol="HTTP",
        LoadBalancerArn=Ref(ApplicationElasticLB),
        DefaultActions=[elb.Action(
            Type="forward",
            TargetGroupArn=Ref(TargetGroupWeb)
        )]
    ))

    template.add_resource(elb.ListenerRule(
        "ListenerRuleApi",
        ListenerArn=Ref(Listener),
        Conditions=[elb.Condition(
            Field="path-pattern",
            Values=["/api/*"])],
        Actions=[elb.Action(
            Type="forward",
            TargetGroupArn=Ref(TargetGroupApi)
        )],
        Priority="1"
    ))

    template.add_output(Output(
        "URL",
        Description="URL of the sample website",
        Value=Join("", ["http://", GetAtt(ApplicationElasticLB, "DNSName")])
    ))
    print(template.to_json())

if __name__ == '__main__':
    main()