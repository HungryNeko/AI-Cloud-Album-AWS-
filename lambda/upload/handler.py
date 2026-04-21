"""
input:
{
    "task_id": "4",
    "zip_link": "<s3 link for zip file>",
    "user_id": "id1"
}

output:
{
    "task_id": "4",
    "run_success": True,
    "images": ["id1", "id2"],
    "msg": "finished"
}
"""
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import boto3

TIME_GUARD_SECONDS = int(os.getenv("LAMBDA_TIME_GUARD_SECONDS", "30"))


def _image_table():
    region = os.getenv("AWS_REGION", "us-west-1")
    table_name = os.getenv("DYNAMODB_IMAGE_TABLE", "ImageMetadata")
    session = boto3.Session(region_name=region)
    return session.resource("dynamodb").Table(table_name)


class handler:

    def __init__(self, event, context):
        self.task_id = ""
        self.zip_link = ""
        self.user_id = ""
        self.context = context
        self.files = []
        self.images = []
        self.msg = ""
        self.run_success = True
        self.read_msg(event)

    def read_msg(self, event: str) -> None:
        # handel json msg
        try:
            payload = event
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                self.msg = "Error when loading msg: event should be dict"
                self.run_success = False
                return
            self.task_id = str(payload.get("task_id", ""))
            self.zip_link = str(payload.get("zip_link", ""))
            self.user_id = str(payload.get("user_id", ""))
            if not self.task_id or not self.zip_link or not self.user_id:
                self.msg = "Error when loading msg: task_id, zip_link and user_id are required"
                self.run_success = False
        except Exception as e:
            self.msg = "Error when loading msg: " + str(e)
            self.run_success = False

    def has_enough_time(self, threshold_seconds=TIME_GUARD_SECONDS) -> bool:
        if self.context is None or not hasattr(self.context, "get_remaining_time_in_millis"):
            self.msg = "Error when loading lambda context: get_remaining_time_in_millis not found"
            self.run_success = False
            return False
        remaining_time_ms = self.context.get_remaining_time_in_millis()
        threshold_ms = threshold_seconds * 1000
        return remaining_time_ms >= threshold_ms

    def load_zip(self) -> list:
        try:
            pass
            # TODO: use the final S3/link helper to read self.zip_link.
            # unzip the zip file and return image file objects or temp paths.
            return []
        except Exception as e:
            self.msg = "Error when loading zip: " + str(e)
            self.run_success = False
            return []

    def write_s3(self, image_id: str, image_file) -> bool:
        try:
            pass
            # TODO: upload image_file to S3 with the final helper.
            return True
        except Exception as e:
            self.msg = "Error when writing to s3: " + str(e)
            self.run_success = False
            return False

    def write_database(self, image_id: str, image_file) -> bool:
        try:
            raw_name = ""
            if hasattr(image_file, "name"):
                raw_name = str(getattr(image_file, "name", "") or "")
            elif isinstance(image_file, (str, Path)):
                raw_name = str(image_file)
            safe_name = os.path.basename(raw_name).replace("/", "_").replace("\\", "_")
            if not safe_name:
                safe_name = image_id
            s3_key = f"{self.user_id}/{image_id}/{safe_name}"
            now = datetime.utcnow().isoformat()
            _image_table().put_item(
                Item={
                    "user_id": self.user_id,
                    "image_id": image_id,
                    "s3_key": s3_key,
                    "status": "uploaded",
                    "label": None,
                    "confidence": None,
                    "location": None,
                    "followup_questions": [],
                    "followup_answers": [],
                    "created_at": now,
                    "updated_at": now,
                }
            )
            return True
        except Exception as e:
            self.msg = "Error when writing to database: " + str(e)
            self.run_success = False
            return False

    def process(self) -> None:
        if not self.has_enough_time():
            self.msg = "Error when processing: not enough remaining time"
            self.run_success = False
            return
        self.images = []
        self.files = self.load_zip()
        if not self.run_success:
            return
        if len(self.files) > 10000:
            self.run_success = False
            self.msg = "Error for too much Files"
            return

        for image_file in self.files:
            if not self.has_enough_time():
                self.msg = "Error when processing: not enough remaining time"
                self.run_success = False
                return

            image_id = str(uuid4())
            if not self.has_enough_time():
                self.msg = "Error when processing: not enough remaining time"
                self.run_success = False
                return
            if not self.write_s3(image_id, image_file):
                return
            if not self.has_enough_time():
                self.msg = "Error when processing: not enough remaining time"
                self.run_success = False
                return
            if not self.write_database(image_id, image_file):
                return
            self.images.append(image_id)

    def run(self):
        if self.run_success == False:
            return
        self.process()
        if self.run_success == False:
            return
        self.msg = "finished"

    def reply(self):
        msg = {
            "task_id": self.task_id,
            "run_success": self.run_success,
            "images": self.images,
            "msg": self.msg,
        }
        return msg


def lambda_handler(event, context):
    pro = handler(event, context)
    pro.run()
    return pro.reply()
