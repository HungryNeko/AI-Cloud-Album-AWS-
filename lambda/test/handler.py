"""
Experiment helper Lambda.

It supports three full-flow test actions:

1. Start upload flow:
{
    "action": "flow_start"
}

2. Check upload/class results and send download:
{
    "action": "flow_check_upload_class_send_download",
    "flow_id": "<flow_id from step 1>"
}

3. Check download results:
{
    "action": "flow_check_download",
    "flow_id": "<flow_id from step 1>"
}

It also supports two older experiments:

1. Full setup flow, which mimics user upload:
{
    "action": "setup_flow"
}

Optional setup overrides:
{
    "action": "setup_flow",
    "user_id": "test_user@example.com",
    "image_id": "test-image-001",
    "source_s3_uri": "s3://ee547-project-group5-ai-cloud-album/lambda_files/130.png",
    "filename": "test.png",
    "status": "processing"
}

The response includes class_event. Send that list directly to the class SQS.

2. Query/reset image state. Default input is exactly the same as class Lambda:
[
    {
        "user_id": "test_2c6c5ba6c5@example.com",
        "image_id": "229b6787-34d3-435c-bbb8-9d0c79eec148",
        "s3_key": "test_2c6c5ba6c5@example.com/229b6787-34d3-435c-bbb8-9d0c79eec148/test.jpg"
    }
]

Default behavior for class-shaped input:
- query each image record by user_id + image_id
- return the status before reset
- set status back to "processing" by default, so class can verify non-uploaded statuses are processable

Other helper actions:
{
    "action": "query",
    "images": [ ...same as class input... ]
}

{
    "action": "reset_status",
    "status": "processing",
    "clear_result": true,
    "images": [ ...same as class input... ]
}

{
    "action": "set_status",
    "status": "failed",
    "images": [ ...same as class input... ]
}
"""
import json
import mimetypes
import os
import base64
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Attr


DEFAULT_AWS_REGION = "us-west-1"
DEFAULT_S3_BUCKET = "ee547-project-group5-ai-cloud-album"
DEFAULT_IMAGE_TABLE = "ImageMetadata"
DEFAULT_USER_TABLE = "Users"
DEFAULT_ZIP_JOBS_TABLE = "ZipJobs"
DEFAULT_PHOTO_FILE = "130.png"
DEFAULT_SOURCE_S3_URI = "s3://ee547-project-group5-ai-cloud-album/lambda_files/130.png"
DEFAULT_FLOW_ZIP_S3_URI = "s3://ee547-project-group5-ai-cloud-album/lambda_files/class_mixed_10.zip"
DEFAULT_UPLOAD_QUEUE_NAME = "zip-upload-queue"
DEFAULT_CLASS_QUEUE_NAME = "image-processing-queue"
DEFAULT_DOWNLOAD_QUEUE_NAME = "download-queue"
DEFAULT_UPLOAD_QUEUE_URL = "https://sqs.us-west-1.amazonaws.com/560720304451/zip-upload-queue"
DEFAULT_CLASS_QUEUE_URL = "https://sqs.us-west-1.amazonaws.com/560720304451/image-processing-queue"
DEFAULT_DOWNLOAD_QUEUE_URL = "https://sqs.us-west-1.amazonaws.com/560720304451/download-queue"
MAX_SCAN_PAGES = int(os.getenv("TEST_HELPER_MAX_SCAN_PAGES", "3"))
HANDLER_VERSION = "test-helper-2026-04-26-01"
DEFAULT_RESET_STATUS = "processing"
DEFAULT_SETUP_STATUS = "processing"
DEFAULT_FLOW_IMAGE_COUNT = int(os.getenv("TEST_HELPER_FLOW_IMAGE_COUNT", "10"))
EMBEDDED_TEST_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGNk"
    "+M8AAwUBAYlBI3YAAAAASUVORK5CYII="
)


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


def _sqs_client():
    return _session().client("sqs")


def _bucket_name():
    return os.getenv("S3_BUCKET", DEFAULT_S3_BUCKET)


def _now():
    return datetime.utcnow().isoformat()


def _json_loads_if_needed(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _json_safe(value):
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return value


def _normalize_image_entry(entry):
    if isinstance(entry, str):
        parts = entry.split("/", 2)
        if len(parts) >= 2:
            return {
                "user_id": parts[0],
                "image_id": parts[1],
                "s3_key": entry,
            }
        return {"user_id": "", "image_id": entry, "s3_key": ""}

    if not isinstance(entry, dict):
        return {"user_id": "", "image_id": "", "s3_key": ""}

    return {
        "user_id": str(entry.get("user_id", "")).strip(),
        "image_id": str(entry.get("image_id", "")).strip(),
        "s3_key": str(entry.get("s3_key", "")).strip(),
        "allow_scan": bool(entry.get("allow_scan", False)),
    }


def _extract_payload(event):
    payload = _json_loads_if_needed(event)

    if isinstance(payload, dict) and "body" in payload:
        body = _json_loads_if_needed(payload.get("body"))
        if isinstance(body, (list, dict)):
            payload = body

    if isinstance(payload, dict) and isinstance(payload.get("Records"), list):
        images = []
        action = str(payload.get("action", "")).strip()
        status = str(payload.get("status", "")).strip()
        clear_result = bool(payload.get("clear_result", False))

        for record in payload.get("Records", []):
            body = record.get("body", record) if isinstance(record, dict) else record
            body = _json_loads_if_needed(body)
            if isinstance(body, list):
                images.extend(body)
            elif isinstance(body, dict):
                action = action or str(body.get("action", "")).strip()
                status = status or str(body.get("status", "")).strip()
                clear_result = clear_result or bool(body.get("clear_result", False))
                if isinstance(body.get("images"), list):
                    images.extend(body.get("images", []))
                elif body.get("image_id"):
                    images.append(body)

        return {
            "action": action or "reset_status",
            "status": status or DEFAULT_RESET_STATUS,
            "clear_result": clear_result,
            "images": images,
        }

    if isinstance(payload, list):
        return {
            "action": "reset_status",
            "status": DEFAULT_RESET_STATUS,
            "clear_result": False,
            "images": payload,
        }

    if isinstance(payload, dict):
        action = str(payload.get("action") or "").strip()
        if action in {
            "flow_start",
            "flow_check_upload_class_send_download",
            "flow_check_download",
            "setup_flow",
        }:
            return payload
        if isinstance(payload.get("images"), list):
            return {
                "action": action or "reset_status",
                "status": str(payload.get("status") or DEFAULT_RESET_STATUS).strip(),
                "clear_result": bool(payload.get("clear_result", False)),
                "images": payload.get("images", []),
            }
        if payload.get("image_id"):
            return {
                "action": action or "reset_status",
                "status": str(payload.get("status") or DEFAULT_RESET_STATUS).strip(),
                "clear_result": bool(payload.get("clear_result", False)),
                "images": [payload],
            }

    return {
        "action": "setup_flow",
    }


def _scan_image_record(table, image_id, max_pages=MAX_SCAN_PAGES):
    start_key = None
    pages = 0
    while True:
        pages += 1
        if pages > max_pages:
            return {}
        scan_kwargs = {
            "FilterExpression": Attr("image_id").eq(image_id),
            "Limit": 25,
            "ConsistentRead": True,
        }
        if start_key is not None:
            scan_kwargs["ExclusiveStartKey"] = start_key
        resp = table.scan(**scan_kwargs)
        items = resp.get("Items", [])
        if items:
            return items[0]
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            return {}


def _get_image_record(table, image):
    user_id = image.get("user_id", "")
    image_id = image.get("image_id", "")
    if user_id and image_id:
        print(json.dumps({
            "version": HANDLER_VERSION,
            "debug": "dynamodb_get_item_start",
            "user_id": user_id,
            "image_id": image_id,
        }))
        item = table.get_item(
            Key={"user_id": user_id, "image_id": image_id},
            ConsistentRead=True,
        ).get("Item")
        print(json.dumps({
            "version": HANDLER_VERSION,
            "debug": "dynamodb_get_item_end",
            "found": bool(item),
        }))
        if item:
            return item
    if image_id and image.get("allow_scan"):
        return _scan_image_record(table, image_id)
    return {}


def _update_status(table, record, status, clear_result):
    user_id = str(record.get("user_id", "")).strip()
    image_id = str(record.get("image_id", "")).strip()
    if not user_id or not image_id:
        raise ValueError("record missing user_id or image_id")

    names = {"#s": "status"}
    values = {":s": status, ":t": _now()}
    update = "SET #s = :s, updated_at = :t"

    if clear_result:
        update += ", label = :empty, confidence = :null, #loc = :null, followup_questions = :empty_list"
        names["#loc"] = "location"
        values[":empty"] = ""
        values[":null"] = None
        values[":empty_list"] = []

    table.update_item(
        Key={"user_id": user_id, "image_id": image_id},
        UpdateExpression=update,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def _photo_path(photo_file):
    path = Path(__file__).resolve().parent / photo_file
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("test photo not found: " + str(path))
    return path


def _content_type(path):
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _hex_prefix(data, size=12):
    return data[:size].hex()


def _parse_s3_uri(uri):
    if not uri.startswith("s3://"):
        raise ValueError("source_s3_uri must start with s3://")
    rest = uri[5:]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise ValueError("source_s3_uri must include bucket and key")
    return bucket, key


def _queue_url(queue_name, env_name, explicit_url=""):
    if explicit_url:
        return explicit_url
    value = os.getenv(env_name, "").strip()
    if value:
        return value
    if queue_name == DEFAULT_UPLOAD_QUEUE_NAME:
        return DEFAULT_UPLOAD_QUEUE_URL
    if queue_name == DEFAULT_CLASS_QUEUE_NAME:
        return DEFAULT_CLASS_QUEUE_URL
    if queue_name == DEFAULT_DOWNLOAD_QUEUE_NAME:
        return DEFAULT_DOWNLOAD_QUEUE_URL
    return _sqs_client().get_queue_url(QueueName=queue_name)["QueueUrl"]


def _send_sqs(queue_name, env_name, body, explicit_url=""):
    queue_url = _queue_url(queue_name, env_name, explicit_url)
    resp = _sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(body),
    )
    return {
        "queue_name": queue_name,
        "queue_url": queue_url,
        "message_id": resp.get("MessageId", ""),
        "body": body,
    }


def _flow_defaults(payload):
    flow_id = str(payload.get("flow_id") or ("flow_" + uuid4().hex[:10])).strip()
    user_id = str(payload.get("user_id") or (flow_id + "@example.com")).strip()
    return {
        "flow_id": flow_id,
        "user_id": user_id,
        "upload_job_id": str(payload.get("upload_job_id") or (flow_id + "_upload")).strip(),
        "download_job_id": str(payload.get("download_job_id") or (flow_id + "_download")).strip(),
        "zip_s3_uri": str(payload.get("zip_s3_uri") or DEFAULT_FLOW_ZIP_S3_URI).strip(),
        "expected_count": int(payload.get("expected_count") or DEFAULT_FLOW_IMAGE_COUNT),
        "upload_queue_url": str(payload.get("upload_queue_url") or "").strip(),
        "download_queue_url": str(payload.get("download_queue_url") or "").strip(),
    }


def _read_zip_job(user_id, job_id):
    if not user_id or not job_id:
        return {}
    return _zip_jobs_table().get_item(
        Key={"user_id": user_id, "job_id": job_id},
        ConsistentRead=True,
    ).get("Item", {})


def _read_user(user_id):
    if not user_id:
        return {}
    return _user_table().get_item(
        Key={"user_id": user_id},
        ConsistentRead=True,
    ).get("Item", {})


def _scan_user_images(user_id, max_pages=20):
    table = _image_table()
    images = []
    start_key = None
    pages = 0
    while True:
        pages += 1
        if pages > max_pages:
            break
        kwargs = {
            "FilterExpression": Attr("user_id").eq(user_id),
            "ConsistentRead": True,
        }
        if start_key is not None:
            kwargs["ExclusiveStartKey"] = start_key
        resp = table.scan(**kwargs)
        images.extend(resp.get("Items", []))
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            break
    images.sort(key=lambda item: str(item.get("created_at", "")))
    return images


def _image_summary(images):
    rows = []
    status_counts = {}
    with_questions = 0
    without_questions = 0
    failed = []
    for item in images:
        status = str(item.get("status", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        questions = item.get("followup_questions", [])
        if questions:
            with_questions += 1
        else:
            without_questions += 1
        if status == "failed":
            failed.append(str(item.get("image_id", "")))
        rows.append({
            "image_id": item.get("image_id", ""),
            "status": status,
            "label": item.get("label", ""),
            "s3_key": item.get("s3_key", ""),
            "followup_questions": questions,
        })
    return {
        "count": len(images),
        "status_counts": status_counts,
        "complete_count": status_counts.get("complete", 0),
        "failed": failed,
        "with_questions": with_questions,
        "without_questions": without_questions,
        "items": rows,
    }


def _make_next(action, flow):
    next_payload = {
        "action": action,
        "flow_id": flow["flow_id"],
        "user_id": flow["user_id"],
        "upload_job_id": flow["upload_job_id"],
        "download_job_id": flow["download_job_id"],
        "expected_count": flow["expected_count"],
    }
    if flow.get("upload_queue_url"):
        next_payload["upload_queue_url"] = flow["upload_queue_url"]
    if flow.get("download_queue_url"):
        next_payload["download_queue_url"] = flow["download_queue_url"]
    return next_payload


def _ensure_flow_user(flow):
    now = _now()
    user_id = flow["user_id"]
    _user_table().put_item(
        Item={
            "user_id": user_id,
            "email": user_id,
            "password_hash": "test-only",
            "created_at": now,
            "updated_at": now,
        }
    )


def _handle_flow_start(payload):
    flow = _flow_defaults(payload)
    bucket, key = _parse_s3_uri(flow["zip_s3_uri"])
    _ensure_flow_user(flow)
    try:
        _s3_client().head_object(Bucket=bucket, Key=key)
        source_exists = True
    except Exception:
        source_exists = False
    message = {
        "user_id": flow["user_id"],
        "job_id": flow["upload_job_id"],
        "s3_key": key,
    }
    sent = _send_sqs(
        DEFAULT_UPLOAD_QUEUE_NAME,
        "SQS_ZIP_UPLOAD_URL",
        message,
        flow["upload_queue_url"],
    )
    return {
        "flow": flow,
        "source": {
            "bucket": bucket,
            "key": key,
            "exists": source_exists,
        },
        "user_created": True,
        "upload_sqs": sent,
        "next": _make_next("flow_check_upload_class_send_download", flow),
    }


def _handle_flow_check_upload_class_send_download(payload):
    flow = _flow_defaults(payload)
    upload_job = _read_zip_job(flow["user_id"], flow["upload_job_id"])
    images = _scan_user_images(flow["user_id"])
    summary = _image_summary(images)
    image_ids = [str(item.get("image_id", "")) for item in images if item.get("image_id")]
    upload_ok = upload_job.get("status") == "complete"
    count_ok = summary["count"] == flow["expected_count"]
    class_ok = (
        count_ok
        and summary["complete_count"] == flow["expected_count"]
        and not summary["failed"]
        and summary["with_questions"] > 0
        and summary["without_questions"] > 0
    )
    ready = upload_ok and class_ok
    download_sqs = {}
    if ready or bool(payload.get("force_download", False)):
        message = {
            "user_id": flow["user_id"],
            "job_id": flow["download_job_id"],
            "image_ids": image_ids,
        }
        download_sqs = _send_sqs(
            DEFAULT_DOWNLOAD_QUEUE_NAME,
            "SQS_DOWNLOAD_URL",
            message,
            flow["download_queue_url"],
        )
    return {
        "flow": flow,
        "upload_job": upload_job,
        "images": summary,
        "checks": {
            "upload_job_complete": upload_ok,
            "expected_image_count": count_ok,
            "all_class_complete": summary["complete_count"] == flow["expected_count"],
            "has_question_images": summary["with_questions"] > 0,
            "has_no_question_images": summary["without_questions"] > 0,
            "ready_for_download": ready,
        },
        "download_sqs": download_sqs,
        "next": _make_next("flow_check_download", flow),
    }


def _handle_flow_check_download(payload):
    flow = _flow_defaults(payload)
    download_job = _read_zip_job(flow["user_id"], flow["download_job_id"])
    user = _read_user(flow["user_id"])
    result_s3_key = str(download_job.get("result_s3_key", ""))
    s3_exists = False
    if result_s3_key:
        try:
            _s3_client().head_object(Bucket=_bucket_name(), Key=result_s3_key)
            s3_exists = True
        except Exception:
            s3_exists = False
    user_zip_download = str(user.get("zip_download", ""))
    return {
        "flow": flow,
        "download_job": download_job,
        "user_zip_download": user_zip_download,
        "checks": {
            "download_job_complete": download_job.get("status") == "complete",
            "result_s3_key_written": bool(result_s3_key),
            "user_zip_download_matches": bool(result_s3_key) and user_zip_download == result_s3_key,
            "result_s3_object_exists": s3_exists,
        },
    }


def _read_test_photo_from_s3(s3, source_s3_uri):
    bucket, key = _parse_s3_uri(source_s3_uri)
    data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("source S3 object is not a PNG image; magic=" + _hex_prefix(data))
    return data, source_s3_uri


def _read_test_photo_from_file(photo_file):
    path = _photo_path(photo_file)
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "file:" + photo_file
    return base64.b64decode(EMBEDDED_TEST_PNG_BASE64), "embedded_png_fallback"


def _setup_flow(payload):
    now = _now()
    user_id = str(payload.get("user_id") or ("test_" + uuid4().hex[:10] + "@example.com"))
    email = str(payload.get("email") or user_id)
    image_id = str(payload.get("image_id") or str(uuid4()))
    photo_file = str(payload.get("photo_file") or DEFAULT_PHOTO_FILE)
    source_s3_uri = str(payload.get("source_s3_uri") or DEFAULT_SOURCE_S3_URI)
    filename = str(payload.get("filename") or photo_file)
    status = str(payload.get("status") or DEFAULT_SETUP_STATUS)
    bucket = str(payload.get("bucket") or _bucket_name())
    s3_key = str(payload.get("s3_key") or f"{user_id}/{image_id}/{filename}")
    password_hash = str(payload.get("password_hash") or "test-only")

    s3 = _s3_client()
    user_table = _user_table()
    image_table = _image_table()

    user_item = {
        "user_id": user_id,
        "email": email,
        "password_hash": password_hash,
        "created_at": now,
        "updated_at": now,
    }
    image_item = {
        "user_id": user_id,
        "image_id": image_id,
        "s3_key": s3_key,
        "status": status,
        "label": None,
        "confidence": None,
        "location": None,
        "followup_questions": [],
        "followup_answers": [],
        "created_at": now,
        "updated_at": now,
    }

    user_table.put_item(Item=user_item)
    try:
        photo_bytes, photo_source = _read_test_photo_from_s3(s3, source_s3_uri)
    except Exception:
        photo_bytes, photo_source = _read_test_photo_from_file(photo_file)

    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=photo_bytes,
        ContentType="image/png",
    )

    uploaded = s3.get_object(Bucket=bucket, Key=s3_key)["Body"].read()
    s3_verified = uploaded == photo_bytes
    if not s3_verified:
        raise RuntimeError("S3 uploaded bytes do not match local test photo bytes")
    if not uploaded.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("S3 object is not a PNG image; magic=" + _hex_prefix(uploaded))

    image_table.put_item(Item=image_item)

    class_event = [{
        "user_id": user_id,
        "image_id": image_id,
        "s3_key": s3_key,
    }]

    return {
        "setup": {
            "user_table": os.getenv("DYNAMODB_USER_TABLE", DEFAULT_USER_TABLE),
            "image_table": os.getenv("DYNAMODB_IMAGE_TABLE", DEFAULT_IMAGE_TABLE),
            "bucket": bucket,
            "photo_file": photo_file,
            "source_s3_uri": source_s3_uri,
            "photo_source": photo_source,
            "photo_size": len(photo_bytes),
            "s3_size": len(uploaded),
            "s3_magic": _hex_prefix(uploaded),
            "s3_verified": s3_verified,
            "user_created": True,
            "s3_uploaded": True,
            "image_created": True,
        },
        "user": {
            "user_id": user_id,
            "email": email,
        },
        "image": image_item,
        "class_event": class_event,
    }


def _handle_image(table, image, action, target_status, clear_result):
    record = _get_image_record(table, image)
    if not record:
        return {
            "input": image,
            "found": False,
            "updated": False,
            "msg": "image record not found; provide user_id + image_id for fast key lookup",
        }

    before = {
        "user_id": record.get("user_id", ""),
        "image_id": record.get("image_id", ""),
        "s3_key": record.get("s3_key", ""),
        "status": record.get("status", ""),
        "label": record.get("label", ""),
        "followup_questions": record.get("followup_questions", []),
        "updated_at": record.get("updated_at", ""),
    }

    updated = False
    if action in {"reset_status", "set_status"}:
        _update_status(table, record, target_status, clear_result)
        updated = True

    after = _get_image_record(table, {
        "user_id": str(record.get("user_id", "")),
        "image_id": str(record.get("image_id", "")),
    })

    return {
        "input": image,
        "found": True,
        "updated": updated,
        "before": before,
        "after": {
            "status": after.get("status", ""),
            "label": after.get("label", ""),
            "followup_questions": after.get("followup_questions", []),
            "updated_at": after.get("updated_at", ""),
        },
    }


def lambda_handler(event, context):
    started = time.time()
    payload = _extract_payload(event)
    action = str(payload.get("action") or "setup_flow").strip()

    result = {
        "version": HANDLER_VERSION,
        "run_success": False,
        "action": action,
        "msg": "",
    }

    try:
        if action == "flow_start":
            result.update(_handle_flow_start(payload))
            result["run_success"] = True
            result["msg"] = "upload sqs sent"
        elif action == "flow_check_upload_class_send_download":
            result.update(_handle_flow_check_upload_class_send_download(payload))
            result["run_success"] = True
            checks = result.get("checks", {})
            result["msg"] = "download sqs sent" if checks.get("ready_for_download") else "not ready for download"
        elif action == "flow_check_download":
            result.update(_handle_flow_check_download(payload))
            result["run_success"] = True
            checks = result.get("checks", {})
            result["msg"] = "download complete" if checks.get("download_job_complete") else "download not complete"
        elif action == "setup_flow":
            result.update(_setup_flow(payload))
            result["run_success"] = True
            result["msg"] = "finished"
        else:
            target_status = payload.get("status") or DEFAULT_RESET_STATUS
            clear_result = bool(payload.get("clear_result", False))
            images = [_normalize_image_entry(entry) for entry in payload.get("images", [])]
            if action not in {"query", "reset_status", "set_status"}:
                raise ValueError("action must be setup_flow, query, reset_status, or set_status")
            if not images:
                raise ValueError("no images provided")

            result.update({
                "target_status": target_status if action != "query" else "",
                "clear_result": clear_result,
                "table": os.getenv("DYNAMODB_IMAGE_TABLE", DEFAULT_IMAGE_TABLE),
                "count": len(images),
                "items": [],
            })

            table = _image_table()
            for image in images:
                if not image.get("image_id"):
                    result["items"].append({
                        "input": image,
                        "found": False,
                        "updated": False,
                        "msg": "missing image_id",
                    })
                    continue
                result["items"].append(
                    _handle_image(table, image, action, target_status, clear_result)
                )

            result["run_success"] = True
            result["msg"] = "finished"
    except Exception as e:
        result["msg"] = str(e)
        err = getattr(e, "response", {}).get("Error", {}) if hasattr(e, "response") else {}
        if err:
            result["aws_error"] = {
                "code": err.get("Code", ""),
                "message": err.get("Message", ""),
            }

    safe = _json_safe(result)
    safe["duration_ms"] = int((time.time() - started) * 1000)
    print(json.dumps(safe))
    return safe
