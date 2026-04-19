import os
from functools import lru_cache
import boto3

@lru_cache(maxsize=1)
def get_session():
    region = os.getenv("AWS_REGION", "us-west-1")
    return boto3.Session(region_name=region)

@lru_cache(maxsize=1)
def s3_client():
    return get_session().client("s3")

@lru_cache(maxsize=1)
def sqs_client():
    return get_session().client("sqs")

@lru_cache(maxsize=1)
def dynamodb_resource():
    return get_session().resource("dynamodb")