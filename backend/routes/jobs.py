from flask import Blueprint, g
from utils.jwt_utils import login_required
from services.db_service import get_job_record, list_jobs_by_user

jobs_bp = Blueprint("jobs", __name__)

@jobs_bp.route("/<job_id>", methods=["GET"])
@login_required
def get_job(job_id):
    item = get_job_record(g.user_id, job_id)
    if not item:
        return {"success": False, "message": "job not found"}, 404
    return {"success": True, "data": item}, 200

@jobs_bp.route("", methods=["GET"])
@login_required
def list_jobs():
    items = list_jobs_by_user(g.user_id)
    return {"success": True, "data": items}, 200