"""
input:
{
    "user_id": "u1",
    "job_id": "job_456",
    "image_ids": ["img1", "img2"]
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
DEFAULT_ZIP_JOBS_TABLE = "ZipJobs"
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


def _zip_jobs_table():
    table_name = os.getenv("DYNAMODB_ZIP_JOBS_TABLE", DEFAULT_ZIP_JOBS_TABLE)
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
        self.job_id = ""
        self.user_id = ""
        self.tasks = []
        self.context = context
        self.files = []
        self.zip_link = ""
        self.zip_s3_key = ""
        self.user_ids = set()
        self.zip_job_started = False
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
            if isinstance(payload, dict) and "body" in payload:
                body = payload.get("body")
                if isinstance(body, str):
                    body = json.loads(body)
                if isinstance(body, dict):
                    payload = body
            if isinstance(payload, dict) and isinstance(payload.get("Records"), list):
                records = payload.get("Records", [])
                if len(records) != 1:
                    self.msg = "Error when loading msg: download handles one SQS record per invocation"
                    self.run_success = False
                    return
                body = records[0].get("body", records[0]) if isinstance(records[0], dict) else records[0]
                if isinstance(body, str):
                    body = json.loads(body)
                payload = body
            if not isinstance(payload, dict):
                self.msg = "Error when loading msg: event should be dict"
                self.run_success = False
                return
            self.user_id = str(payload.get("user_id", "")).strip()
            self.job_id = str(payload.get("job_id") or payload.get("task_id") or "").strip()
            self.task_id = self.job_id
            images = payload.get("image_ids", payload.get("images", []))
            if not self.user_id or not self.job_id:
                self.msg = "Error when loading msg: user_id and job_id are required"
                self.run_success = False
                return
            if not isinstance(images, list):
                self.msg = "Error when loading msg: image_ids should be list"
                self.run_success = False
                return
            self.tasks = []
            for entry in images:
                if not isinstance(entry, str) or not entry:
                    self.msg = "Error when loading msg: image_ids must contain non-empty image_id strings"
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
            return {}
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
                    user_id = str(item.get("user_id") or self.user_id)
                    direct_s3_key = str(item.get("s3_key", ""))
                else:
                    user_id, image_id, direct_s3_key = _parse_image_input(str(item))
                    if not user_id:
                        user_id = self.user_id
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

    def write_zip_job(self, status: str, result_s3_key: str = "") -> bool:
        try:
            if not self.user_id or not self.job_id:
                raise ValueError("user_id and job_id are required")
            now = datetime.utcnow().isoformat()
            table = _zip_jobs_table()
            if status == "processing" and not self.zip_job_started:
                table.put_item(
                    Item={
                        "user_id": self.user_id,
                        "job_id": self.job_id,
                        "type": "download",
                        "status": status,
                        "result_s3_key": result_s3_key,
                        "total_files": len(self.tasks),
                        "image_ids": self.tasks,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                self.zip_job_started = True
                return True

            update = "SET #s = :s, updated_at = :t"
            names = {"#s": "status"}
            values = {
                ":s": status,
                ":t": now,
            }
            if result_s3_key:
                update += ", result_s3_key = :r"
                values[":r"] = result_s3_key
            table.update_item(
                Key={"user_id": self.user_id, "job_id": self.job_id},
                UpdateExpression=update,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
            return True
        except Exception as e:
            self.msg = "Error when writing zip job database: " + str(e)
            self.run_success = False
            return False

    def mark_zip_job_failed(self) -> None:
        if not self.user_id or not self.job_id:
            return
        previous_msg = self.msg
        try:
            table = _zip_jobs_table()
            now = datetime.utcnow().isoformat()
            if not self.zip_job_started:
                table.put_item(
                    Item={
                        "user_id": self.user_id,
                        "job_id": self.job_id,
                        "type": "download",
                        "status": "failed",
                        "result_s3_key": self.zip_s3_key,
                        "total_files": len(self.tasks),
                        "image_ids": self.tasks,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                self.zip_job_started = True
                return
            table.update_item(
                Key={"user_id": self.user_id, "job_id": self.job_id},
                UpdateExpression="SET #s = :s, updated_at = :t",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": "failed",
                    ":t": now,
                },
            )
        except Exception as e:
            self.msg = previous_msg or ("Error when writing failed zip job status: " + str(e))

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
        self.user_ids.add(self.user_id)
        if not self.write_zip_job("processing"):
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
        if not self.write_zip_job("complete", self.zip_s3_key):
            return

    def run(self):
        if self.run_success == False:
            return
        if len(self.tasks) > 10000:
            self.run_success = False
            self.msg = "Error for too much Files"
            self.mark_zip_job_failed()
            return
        self.process()
        if self.run_success == False:
            self.mark_zip_job_failed()
            return
        self.msg = "finished"

    def reply(self):
        msg = {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "job_id": self.job_id,
            "run_success": self.run_success,
            "zip_link": self.zip_link,
            "zip_s3_key": self.zip_s3_key,
            "zip_job": {
                "table": os.getenv("DYNAMODB_ZIP_JOBS_TABLE", DEFAULT_ZIP_JOBS_TABLE),
                "status": "complete" if self.run_success else "failed",
                "type": "download",
                "result_s3_key": self.zip_s3_key,
                "total_files": len(self.tasks),
                "image_ids": self.tasks,
            },
            "msg": self.msg,
        }
        return msg


def lambda_handler(event, context):
    pro = handler(event, context)
    pro.run()
    return pro.reply()
