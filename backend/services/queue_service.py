import json
from services.aws_clients import sqs_client
from flask import current_app

def send_job_to_sqs_image(payload: dict):
    sqs = sqs_client()
    resp = sqs.send_message(
        QueueUrl=current_app.config["SQS_IMAGE_PROCESSING_URL"],
        MessageBody=json.dumps([payload])
    )
    return {
        "message_id": resp.get("MessageId"),
        "queue_url": current_app.config["SQS_IMAGE_PROCESSING_URL"]
    }

def send_job_to_sqs_zip_upload(payload: dict):
    sqs = sqs_client()
    resp = sqs.send_message(
        QueueUrl=current_app.config["SQS_ZIP_UPLOAD_URL"],
        MessageBody=json.dumps(payload)
    )
    return {
        "message_id": resp.get("MessageId"),
        "queue_url": current_app.config["SQS_ZIP_UPLOAD_URL"]
    }

def send_job_to_sqs_download(payload: dict):
    sqs = sqs_client()
    resp = sqs.send_message(
        QueueUrl=current_app.config["SQS_DOWNLOAD_URL"],
        MessageBody=json.dumps(payload)
    )
    return {
        "message_id": resp.get("MessageId"),
        "queue_url": current_app.config["SQS_DOWNLOAD_URL"]
    }