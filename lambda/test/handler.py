"""
Experiment helper Lambda.

It supports two kinds of experiments:

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
    "status": "uploaded"
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
- set status back to "uploaded"

Other helper actions:
{
    "action": "query",
    "images": [ ...same as class input... ]
}

{
    "action": "reset_status",
    "status": "uploaded",
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
DEFAULT_PHOTO_FILE = "130.png"
DEFAULT_SOURCE_S3_URI = "s3://ee547-project-group5-ai-cloud-album/lambda_files/130.png"
MAX_SCAN_PAGES = int(os.getenv("TEST_HELPER_MAX_SCAN_PAGES", "3"))
HANDLER_VERSION = "test-helper-2026-04-25-01"
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


def _s3_client():
    return _session().client("s3")


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
            "status": status or "uploaded",
            "clear_result": clear_result,
            "images": images,
        }

    if isinstance(payload, list):
        return {
            "action": "reset_status",
            "status": "uploaded",
            "clear_result": False,
            "images": payload,
        }

    if isinstance(payload, dict):
        action = str(payload.get("action") or "").strip()
        if action == "setup_flow":
            return payload
        if isinstance(payload.get("images"), list):
            return {
                "action": action or "reset_status",
                "status": str(payload.get("status") or "uploaded").strip(),
                "clear_result": bool(payload.get("clear_result", False)),
                "images": payload.get("images", []),
            }
        if payload.get("image_id"):
            return {
                "action": action or "reset_status",
                "status": str(payload.get("status") or "uploaded").strip(),
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
    status = str(payload.get("status") or "uploaded")
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
        if action == "setup_flow":
            result.update(_setup_flow(payload))
            result["run_success"] = True
            result["msg"] = "finished"
        else:
            target_status = payload.get("status") or "uploaded"
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
