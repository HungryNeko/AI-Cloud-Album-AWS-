from flask import Blueprint, g
from utils.jwt_utils import login_required
from services.collection_service import get_collections

collections_bp = Blueprint("collections", __name__)

@collections_bp.route("", methods=["GET"])
@login_required
def list_collections():
    collections = get_collections(g.user_id)
    return {
        "success": True, 
        "data": collections
    }, 200