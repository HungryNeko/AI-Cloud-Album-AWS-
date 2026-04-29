from flask import Blueprint, request, g
from utils.jwt_utils import login_required
from services.image_service import create_upload_job, create_upload_zip_job, create_download_job, search_images, delete_image_record
from services.db_service import get_image_record, list_images_by_user, add_followup_answer

images_bp = Blueprint("images", __name__)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@images_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    if request.content_length and request.content_length > MAX_FILE_SIZE:
        return {"success": False, "message": "file too large (Max 50MB)"}, 413

    if "file" not in request.files:
        return {"success": False, "message": "file is required"}, 400

    result = create_upload_job(request.files["file"], g.user_id)
    if not result["ok"]:
        return {"success": False, "message": result["message"]}, 400

    return {
        "success": True,
        "message": "uploaded",
        "data": result["data"]
    }, 201

@images_bp.route("/<image_id>", methods=["GET"])
@login_required
def get_image(image_id):
    item = get_image_record(g.user_id, image_id)
    if not item:
        return {"success": False, "message": "image not found"}, 404
    return {"success": True, "data": item}, 200

@images_bp.route("", methods=["GET"])
@login_required
def list_images():
    items = list_images_by_user(g.user_id)
    return {"success": True, "data": items}, 200

@images_bp.route("/<image_id>/result", methods=["GET"])
@login_required
def get_image_result(image_id):
    item = get_image_record(g.user_id, image_id)
    if not item:
        return {"success": False, "message": "image not found"}, 404
    
    result = {
        "image_id": item.get("image_id"),
        "status": item.get("status"),
        "label": item.get("label"),
        "followup_questions": item.get("followup_questions", [])
    }

    return {"success": True, "data": result}, 200

@images_bp.route("/<image_id>/followup", methods=["POST"])
@login_required
def followup(image_id):
    data = request.get_json(silent=True) or {}
    item = add_followup_answer(g.user_id, image_id, data)
    if not item:
        return {"success": False, "message": "image not found"}, 404
    return {"success": True, "data": item}, 200

@images_bp.route("/upload-zip", methods=["POST"])
@login_required
def upload_zip():
    if request.content_length and request.content_length > MAX_FILE_SIZE:
        return {"success": False, "message": "file too large (Max 50MB)"}, 413
    if "file" not in request.files:
        return {"success": False, "message": "file is required"}, 400
    result = create_upload_zip_job(request.files["file"], g.user_id)
    if not result["ok"]:
        return {"success": False, "message": result["message"]}, 400
    return {
        "success": True,
        "message": "uploaded",
        "data": result["data"]
    }, 201

@images_bp.route("/download", methods=["POST"])
@login_required
def download():
    data = request.get_json(silent=True) or {}

    if "image_ids" not in data:
        return {"success": False, "message": "image_ids is required"}, 400

    result = create_download_job(data["image_ids"], g.user_id)

    if not result["ok"]:
        return {"success": False, "message": result["message"]}, 400

    return {
        "success": True,
        "message": "download job created",
        "data": result["data"]
    }, 201

@images_bp.route("/search", methods=["GET"])
@login_required
def search():
    items = search_images(request.args, g.user_id)
    return {"success": True, "data": items}, 200

@images_bp.route("/<image_id>", methods=["DELETE"])
@login_required
def delete_image(image_id):
    result = delete_image_record(g.user_id, image_id)
    if not result["ok"]:
        return {"success": False, "message": result["message"]}, 400
    return {
        "success": True,
        "message": "deleted",
        "data": result["data"]
    }, 200