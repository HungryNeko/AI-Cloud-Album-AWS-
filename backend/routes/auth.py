from flask import Blueprint, request
from utils.jwt_utils import generate_token
from services.db_service import create_user, verify_user

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return {"success": False, "message": "email and password required"}, 400

    user = create_user(email, password)
    token = generate_token(user["user_id"])

    return {
        "success": True,
        "message": "registered",
        "data": {
            "user_id": user["user_id"],
            "token": token
        }
    }, 201

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return {"success": False, "message": "email and password required"}, 400

    user = verify_user(email, password)
    if not user:
        return {"success": False, "message": "invalid credentials"}, 401

    token = generate_token(user["user_id"])

    return {
        "success": True,
        "message": "login success",
        "data": {
            "user_id": user["user_id"],
            "token": token
        }
    }, 200