import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET = os.getenv("JWT_SECRET")

    AWS_REGION = os.getenv("AWS_REGION")
    S3_BUCKET = os.getenv("S3_BUCKET")
    SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
    DYNAMODB_USER_TABLE = os.getenv("DYNAMODB_USER_TABLE")
    DYNAMODB_IMAGE_TABLE = os.getenv("DYNAMODB_IMAGE_TABLE")