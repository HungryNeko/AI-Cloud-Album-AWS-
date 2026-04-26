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
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import boto3

TIME_GUARD_SECONDS = int(os.getenv("LAMBDA_TIME_GUARD_SECONDS", "30"))
DEFAULT_AWS_REGION = "us-west-1"
DEFAULT_S3_BUCKET = "ee547-project-group5-ai-cloud-album"
DEFAULT_IMAGE_TABLE = "ImageMetadata"
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _session():
    region = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
    return boto3.Session(region_name=region)


def _image_table():
    table_name = os.getenv("DYNAMODB_IMAGE_TABLE", DEFAULT_IMAGE_TABLE)
    return _session().resource("dynamodb").Table(table_name)


def _s3_client():
    return _session().client("s3")


def _bucket_name():
    return os.getenv("S3_BUCKET", DEFAULT_S3_BUCKET)


def _parse_s3_link(link: str) -> tuple[str, str]:
    parsed = urlparse(link)
    if parsed.scheme == "s3":
        return parsed.netloc, parsed.path.lstrip("/")
    if parsed.scheme in ("http", "https"):
        host = parsed.netloc
        path = parsed.path.lstrip("/")
        suffix = ".s3." + os.getenv("AWS_REGION", DEFAULT_AWS_REGION) + ".amazonaws.com"
        if host.endswith(suffix):
            return host[: -len(suffix)], unquote(path)
        if ".s3." in host and host.endswith(".amazonaws.com"):
            return host.split(".s3.", 1)[0], unquote(path)
    raise ValueError("zip_link must be an s3:// URI or S3 object URL")


def _safe_file_name(raw_name: str, fallback: str) -> str:
    safe_name = os.path.basename(raw_name).replace("/", "_").replace("\\", "_")
    return safe_name or fallback


def _s3_key_for_image(user_id: str, image_id: str, image_file) -> str:
    raw_name = ""
    if hasattr(image_file, "name"):
        raw_name = str(getattr(image_file, "name", "") or "")
    elif isinstance(image_file, (str, Path)):
        raw_name = str(image_file)
    safe_name = _safe_file_name(raw_name, image_id)
    return f"{user_id}/{image_id}/{safe_name}"


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
            source_bucket, source_key = _parse_s3_link(self.zip_link)
            if self.temp_dir is None:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="lambda_upload_"))
            zip_path = self.temp_dir / f"{self.task_id}_{uuid4().hex}.zip"
            with zip_path.open("wb") as f:
                _s3_client().download_fileobj(source_bucket, source_key, f)

            extract_dir = self.temp_dir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            files = []
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    target = (extract_dir / member.filename).resolve()
                    if extract_dir.resolve() not in target.parents:
                        raise ValueError("zip contains unsafe path: " + member.filename)
                    if target.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src, target.open("wb") as dst:
                        dst.write(src.read())
                    files.append(target)
            return files
        except Exception as e:
            self.msg = "Error when loading zip: " + str(e)
            self.run_success = False
            return []

    def write_s3(self, image_id: str, image_file) -> bool:
        try:
            bucket = _bucket_name()
            s3_key = _s3_key_for_image(self.user_id, image_id, image_file)
            _s3_client().upload_file(str(Path(image_file)), bucket, s3_key)
            return True
        except Exception as e:
            self.msg = "Error when writing to s3: " + str(e)
            self.run_success = False
            return False

    def write_database(self, image_id: str, image_file) -> bool:
        try:
            s3_key = _s3_key_for_image(self.user_id, image_id, image_file)
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
