from flask import Blueprint, request, g
from utils.jwt_utils import login_required
from services.image_service import create_upload_job
from services.db_service import get_image_record, list_images_by_user, add_followup_answer

images_bp = Blueprint("images", __name__)

@images_bp.route("/upload", methods=["POST"])
@login_required
def upload():
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

@images_bp.route("/<image_id>/followup", methods=["POST"])
@login_required
def followup(image_id):
    data = request.get_json(silent=True) or {}
    item = add_followup_answer(g.user_id, image_id, data)
    if not item:
        return {"success": False, "message": "image not found"}, 404
    return {"success": True, "data": item}, 200