import uuid
from datetime import datetime
from services.storage_service import upload_file_to_s3
from services.queue_service import send_job_to_sqs_image, send_job_to_sqs_zip_upload, send_job_to_sqs_download
from services.db_service import create_image_record, update_image_status, create_job_record, update_job_status, get_image_record, list_images_by_user

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

def allowed_file(filename: str):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def create_upload_job(file_obj, user_id: str):
    if not file_obj or not file_obj.filename:
        return {"ok": False, "message": "file is required"}

    if not allowed_file(file_obj.filename):
        return {"ok": False, "message": "invalid file type"}

    image_id = str(uuid.uuid4())
    safe_name = file_obj.filename.replace("/", "_").replace("\\", "_")
    s3_key = f"{user_id}/{image_id}/{safe_name}"

    upload_file_to_s3(file_obj, s3_key)

    create_image_record({
        "user_id": user_id,
        "image_id": image_id,
        "s3_key": s3_key,
        "status": "uploaded",
        "label": None,
        "confidence": None,
        "location": None,
        "followup_questions": [],
        "followup_answers": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    })

    send_job_to_sqs_image({
        "user_id": user_id,
        "image_id": image_id,
        "s3_key": s3_key
    })

    update_image_status(user_id, image_id, "processing")

    return {
        "ok": True,
        "data": {
            "image_id": image_id,
            "status": "processing",
            "s3_key": s3_key
        }
    }


def create_upload_zip_job(file_obj, user_id: str):
    if not file_obj or not file_obj.filename:
        return {"ok": False, "message": "file is required"}

    if not file_obj.filename.endswith(".zip"):
        return {"ok": False, "message": "invalid file type"}

    job_id = str(uuid.uuid4())
    s3_key = f"uploads/zips/{user_id}/{job_id}.zip"

    upload_file_to_s3(file_obj, s3_key)

    create_job_record({
        "user_id": user_id,
        "job_id": job_id,
        "type": "zip_upload",
        "status": "uploaded",
        "s3_key": s3_key,
        "result_s3_key": None,
        "total_files": 0,
        "processed_files": 0,
        "image_ids": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    })

    send_job_to_sqs_zip_upload({
        "user_id": user_id,
        "job_id": job_id,
        "s3_key": s3_key
    })

    update_job_status(user_id, job_id, "processing")

    return {
        "ok": True,
        "data": {
            "job_id": job_id,
            "status": "processing",
            "s3_key": s3_key
        }
    }


def create_download_job(image_ids, user_id: str):
    if not image_ids or not isinstance(image_ids, list):
        return {"ok": False, "message": "invalid image_ids"}

    if len(image_ids) == 0:
        return {"ok": False, "message": "invalid image_ids"}

    job_id = str(uuid.uuid4())

    create_job_record({
        "user_id": user_id,
        "job_id": job_id,
        "type": "download",
        "status": "uploaded",

        "s3_key": None,
        "result_s3_key": None,

        "total_files": len(image_ids),
        "processed_files": 0,

        "image_ids": image_ids,

        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    })

    send_job_to_sqs_download({
        "user_id": user_id,
        "job_id": job_id,
        "image_ids": image_ids
    })

    update_job_status(user_id, job_id, "processing")

    return {
        "ok": True,
        "data": {
            "job_id": job_id,
            "status": "processing"
        }
    }


def search_images(params, user_id):
    items = list_images_by_user(user_id)

    q = (params.get("q") or "").strip().lower()
    if not q:
        return []

    keywords = [k for k in q.split() if k]

    results = []
    for item in items:
        texts = []

        label = item.get("label")
        if label:
            texts.append(label)

        answers = item.get("followup_answers", [])
        for ans in answers:
            texts.append(str(ans))

        combined = " ".join(texts).lower()

        if all(k in combined for k in keywords):
            results.append({
                "image_id": item.get("image_id"),
                "label": item.get("label"),
                "s3_key": item.get("s3_key")
            })

    return results


def delete_image_record(user_id, image_id):
    item = get_image_record(user_id, image_id)

    if not item:
        return {"ok": False, "message": "invalid image_id"}

    update_image_status(user_id, image_id, "deleted")

    return {
        "ok": True,
        "data": {
            "image_id": image_id
        }
    }