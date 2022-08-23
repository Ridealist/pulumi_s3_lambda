"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws
import pulumi_docker as docker

# Create an AWS resource (S3 Bucket)
bucket = aws.s3.Bucket("bucket")


# Create an ECS repo (Elastic Container Service)
repo = aws.ecr.Repository("sampleapp")
ecr_creds = aws.ecr.get_authorization_token()


# Create Docker Image in currecnt repository
image = docker.Image(
    "sampleapp",
    build="./build-ffmpeg",
    image_name=repo.repository_url,
    registry=docker.ImageRegistry(
        server=repo.repository_url,
        username=ecr_creds.user_name,
        password=ecr_creds.password,
    ),
)

# IAM 권한 부여
role = aws.iam.Role(
    "thumbnailerRole",
    assume_role_policy=f"""{{
    "Version": "2012-10-17",
    "Statement": [
        {{
            "Effect": "Allow",
            "Principal": {{ "Service": "lambda.amazonaws.com" }},
            "Action": "sts:AssumeRole"
        }}
    ]
}}""",
)

aws.iam.RolePolicyAttachment(
    "lambdaBasicRole",
    role=role.name,
    policy_arn=aws.iam.ManagedPolicy.AWS_LAMBDA_BASIC_EXECUTION_ROLE,
)

aws.iam.RolePolicyAttachment(
    "lambdaS3Role",
    role=role.name,
    policy_arn=aws.iam.ManagedPolicy.AMAZON_S3_FULL_ACCESS,
)


# Define lambda function
thumbnailer = aws.lambda_.Function(
    "thumbnailer",
    package_type="Image",
    image_uri=image.image_name,
    role=role.arn,
    timeout=60,
)


# Allow Permission to lambda for access s3 bucket
allow_bucket = aws.lambda_.Permission(
    "allowBucket",
    action="lambda:InvokeFunction",
    function=thumbnailer.arn,
    principal="s3.amazonaws.com",
    source_arn=bucket.arn,
)


# Connect trigger in s3 bucket that call lambda function
bucket_notification = aws.s3.BucketNotification(
    "bucketNotification",
    bucket=bucket.id,
    lambda_functions=[
        aws.s3.BucketNotificationLambdaFunctionArgs(
            lambda_function_arn=thumbnailer.arn,
            events=["s3:ObjectCreated:*"],
            filter_suffix=".mp4",
        )
    ],
    opts=pulumi.ResourceOptions(depends_on=[allow_bucket]),
)


pulumi.export("bucketName", bucket.bucket)
