"""
input:
{
    "task_id": "3",
    "images": ["id1", "id2"]
}

output:
{
    "task_id": "3",
    "run_success": True,
    "zip_link": "<s3 link for zip file>",
    "zip_s3_key": "<s3 key for zip file>",
    "msg": "finished"
}
"""
import json
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Attr

TIME_GUARD_SECONDS = int(os.getenv("LAMBDA_TIME_GUARD_SECONDS", "30"))
DEFAULT_AWS_REGION = "us-west-1"
DEFAULT_S3_BUCKET = "ee547-project-group5-ai-cloud-album"
DEFAULT_IMAGE_TABLE = "ImageMetadata"
DEFAULT_USER_TABLE = "Users"
IMAGE_REF_SEPARATOR = "#"


def _session():
    region = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
    return boto3.Session(region_name=region)


def _image_table():
    table_name = os.getenv("DYNAMODB_IMAGE_TABLE", DEFAULT_IMAGE_TABLE)
    return _session().resource("dynamodb").Table(table_name)


def _user_table():
    table_name = os.getenv("DYNAMODB_USER_TABLE", DEFAULT_USER_TABLE)
    return _session().resource("dynamodb").Table(table_name)


def _s3_client():
    return _session().client("s3")


def _bucket_name():
    return os.getenv("S3_BUCKET", DEFAULT_S3_BUCKET)


def _parse_image_ref(value: str) -> tuple[str, str]:
    if IMAGE_REF_SEPARATOR in value:
        user_id, image_id = value.split(IMAGE_REF_SEPARATOR, 1)
        if user_id and image_id:
            return user_id, image_id
    return "", value


def _parse_image_input(value: str) -> tuple[str, str, str]:
    user_id, image_id = _parse_image_ref(value)
    if user_id:
        return user_id, image_id, ""
    parts = value.split("/", 2)
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1], value
    return "", value, ""


class handler:

    def __init__(self, event, context):
        self.task_id = ""
        self.tasks = []
        self.context = context
        self.files = []
        self.zip_link = ""
        self.zip_s3_key = ""
        self.user_ids = set()
        self.msg = ""
        self.run_success = True
        self.temp_dir = None
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
            images = payload.get("images", [])
            if not self.task_id:
                self.msg = "Error when loading msg: task_id is required"
                self.run_success = False
                return
            if not isinstance(images, list):
                self.msg = "Error when loading msg: images should be list"
                self.run_success = False
                return
            self.tasks = []
            for entry in images:
                if not isinstance(entry, str) or not entry:
                    self.msg = "Error when loading msg: images must contain non-empty image_id strings"
                    self.run_success = False
                    return
                self.tasks.append(entry)
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

    def _resolve_record(self, table, image_id: str, user_id: str = "") -> dict:
        if not self.has_enough_time():
            self.msg = "Error when loading images: not enough remaining time"
            self.run_success = False
            return {}
        if user_id:
            resp = table.get_item(Key={"user_id": user_id, "image_id": image_id})
            item = resp.get("Item")
            if item:
                return item
        start_key = None
        while True:
            if not self.has_enough_time():
                self.msg = "Error when loading images: not enough remaining time"
                self.run_success = False
                return {}
            kwargs = {
                "FilterExpression": Attr("image_id").eq(image_id),
                "ProjectionExpression": "user_id,image_id,s3_key",
                "Limit": 1,
            }
            if start_key is not None:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**kwargs)
            items = resp.get("Items", [])
            if items:
                return items[0]
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        return {}

    def load_images(self, image_list: list) -> list:
        try:
            bucket = _bucket_name()
            table = _image_table()
            s3 = _s3_client()
            if self.temp_dir is None:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="lambda_download_"))
            files = []
            for item in image_list:
                if not self.has_enough_time():
                    self.msg = "Error when loading images: not enough remaining time"
                    self.run_success = False
                    return files
                image_id = ""
                user_id = ""
                direct_s3_key = ""
                if isinstance(item, dict):
                    image_id = str(item.get("image_id", ""))
                    user_id = str(item.get("user_id", ""))
                    direct_s3_key = str(item.get("s3_key", ""))
                else:
                    user_id, image_id, direct_s3_key = _parse_image_input(str(item))
                if not image_id:
                    raise ValueError("image_id is required")
                record = self._resolve_record(table, image_id, user_id)
                if not self.run_success:
                    return files
                if not record and direct_s3_key and user_id:
                    record = {
                        "user_id": user_id,
                        "image_id": image_id,
                        "s3_key": direct_s3_key,
                    }
                record_user_id = str(record.get("user_id", "") or user_id).strip()
                if record_user_id:
                    self.user_ids.add(record_user_id)
                s3_key = str(record.get("s3_key", ""))
                if not s3_key:
                    raise ValueError("s3_key not found for image_id: " + image_id)
                file_name = Path(s3_key).name
                if not file_name:
                    file_name = image_id
                local_path = self.temp_dir / f"{image_id}_{file_name}"
                if not self.has_enough_time():
                    self.msg = "Error when loading images: not enough remaining time"
                    self.run_success = False
                    return files
                with local_path.open("wb") as f:
                    s3.download_fileobj(bucket, s3_key, f)
                files.append(local_path)
            return files
        except Exception as e:
            self.msg = "Error when loading images: " + str(e)
            self.run_success = False
            return []

    def make_zip(self, files: list):
        try:
            if self.temp_dir is None:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="lambda_download_"))
            zip_path = self.temp_dir / f"{self.task_id}_{uuid4().hex}.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in files:
                    if not self.has_enough_time():
                        self.msg = "Error when making zip: not enough remaining time"
                        self.run_success = False
                        return None
                    p = Path(file_path)
                    zf.write(p, arcname=p.name)
            return zip_path
        except Exception as e:
            self.msg = "Error when making zip: " + str(e)
            self.run_success = False
            return None

    def write_s3(self, zip_file) -> str:
        try:
            if not self.has_enough_time():
                self.msg = "Error when writing to s3: not enough remaining time"
                self.run_success = False
                return ""
            bucket = _bucket_name()
            key_prefix = os.getenv("DOWNLOAD_ZIP_PREFIX", "downloads").strip("/")
            if not key_prefix:
                key_prefix = "downloads"
            date_part = datetime.utcnow().strftime("%Y%m%d")
            s3_key = f"{key_prefix}/{date_part}/{self.task_id}_{uuid4().hex}.zip"
            zip_path = Path(zip_file)
            _s3_client().upload_file(str(zip_path), bucket, s3_key)
            self.zip_s3_key = s3_key
            return f"s3://{bucket}/{s3_key}"
        except Exception as e:
            self.msg = "Error when writing to s3: " + str(e)
            self.run_success = False
            return ""

    def write_user_download_key(self) -> bool:
        try:
            if not self.has_enough_time():
                self.msg = "Error when writing to user database: not enough remaining time"
                self.run_success = False
                return False
            if not self.zip_s3_key:
                raise ValueError("zip_s3_key is empty")
            if not self.user_ids:
                raise ValueError("user_id not found for download task")
            table = _user_table()
            now = datetime.utcnow().isoformat()
            for user_id in sorted(self.user_ids):
                table.update_item(
                    Key={"user_id": user_id},
                    UpdateExpression="SET zip_download = :z, updated_at = :t",
                    ConditionExpression="attribute_exists(user_id)",
                    ExpressionAttributeValues={
                        ":z": self.zip_s3_key,
                        ":t": now,
                    },
                )
            return True
        except Exception as e:
            self.msg = "Error when writing to user database: " + str(e)
            self.run_success = False
            return False

    def process(self) -> None:
        if not self.has_enough_time():
            self.msg = "Error when processing: not enough remaining time"
            self.run_success = False
            return

        self.files = self.load_images(self.tasks)
        if not self.run_success:
            return

        if not self.has_enough_time():
            self.msg = "Error when processing: not enough remaining time"
            self.run_success = False
            return
        zip_file = self.make_zip(self.files)
        if not self.run_success:
            return

        if not self.has_enough_time():
            self.msg = "Error when processing: not enough remaining time"
            self.run_success = False
            return
        self.zip_link = self.write_s3(zip_file)
        if not self.run_success:
            return

        if not self.has_enough_time():
            self.msg = "Error when processing: not enough remaining time"
            self.run_success = False
            return
        if not self.write_user_download_key():
            return

    def run(self):
        if self.run_success == False:
            return
        if len(self.tasks) > 10000:
            self.run_success = False
            self.msg = "Error for too much Files"
            return
        self.process()
        if self.run_success == False:
            return
        self.msg = "finished"

    def reply(self):
        msg = {
            "task_id": self.task_id,
            "run_success": self.run_success,
            "zip_link": self.zip_link,
            "zip_s3_key": self.zip_s3_key,
            "msg": self.msg,
        }
        return msg


def lambda_handler(event, context):
    pro = handler(event, context)
    pro.run()
    return pro.reply()
