import json
from services.aws_clients import sqs_client
from flask import current_app

def send_job_to_sqs(payload: dict):
    sqs = sqs_client()
    resp = sqs.send_message(
        QueueUrl=current_app.config["SQS_QUEUE_URL"],
        MessageBody=json.dumps(payload)
    )
    return {
        "message_id": resp.get("MessageId"),
        "queue_url": current_app.config["SQS_QUEUE_URL"]
    }