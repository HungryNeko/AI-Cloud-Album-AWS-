from flask import Blueprint, request, g
from utils.jwt_utils import login_required
from services.storage_service import generate_presigned

utils_bp = Blueprint("utils", __name__)

@utils_bp.route("/presigned-url", methods=["POST"])
@login_required
def get_presigned_url():
    data = request.get_json(silent=True) or {}

    if "s3_key" not in data:
        return {"success": False, "message": "s3_key required"}, 400

    result = generate_presigned(data["s3_key"])

    if not result["ok"]:
        return {"success": False, "message": result["message"]}, 400

    return {
        "success": True,
        "data": {
            "url": result["url"]
        }
    }, 200