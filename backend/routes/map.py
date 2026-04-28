from flask import Blueprint, g
from utils.jwt_utils import login_required
from services.db_service import list_images_by_user

map_bp = Blueprint("map", __name__)

@map_bp.route("/points", methods=["GET"])
@login_required
def get_map_points():
    items = list_images_by_user(g.user_id)

    points = []

    for item in items:
        loc = item.get("location")

        if loc and "lat" in loc and "lng" in loc:
            points.append({
                "image_id": item.get("image_id"),
                "lat": loc.get("lat"),
                "lng": loc.get("lng")
            })

    return {
        "success": True,
        "data": points
    }, 200