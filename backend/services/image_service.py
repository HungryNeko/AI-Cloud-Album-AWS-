import uuid
from datetime import datetime
from services.storage_service import upload_file_to_s3
from services.queue_service import send_job_to_sqs
from services.db_service import create_image_record, update_image_status

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

    send_job_to_sqs({
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