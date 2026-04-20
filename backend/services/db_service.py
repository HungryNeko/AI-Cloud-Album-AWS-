from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from services.aws_clients import dynamodb_resource
from flask import current_app
from botocore.exceptions import ClientError

def _user_table():
    return dynamodb_resource().Table(current_app.config["DYNAMODB_USER_TABLE"])

def _image_table():
    return dynamodb_resource().Table(current_app.config["DYNAMODB_IMAGE_TABLE"])

# ---------- Users ----------
def create_user(email: str, password: str):
    user_id = email
    item = {
        "user_id": user_id,
        "email": email,
        "password_hash": generate_password_hash(password),
        "created_at": datetime.utcnow().isoformat()
    }
    try:
        _user_table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(user_id)"
        )
        return item
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise

def get_user_by_email(email: str):
    resp = _user_table().get_item(Key={"user_id": email})
    item = resp.get("Item", [])
    return item

def verify_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user

# ---------- Images ----------
def create_image_record(item: dict):
    _image_table().put_item(Item=item)
    return item

def get_image_record(user_id: str, image_id: str):
    resp = _image_table().get_item(
        Key={"user_id": user_id, "image_id": image_id}
    )
    return resp.get("Item")

def list_images_by_user(user_id: str):
    resp = _image_table().query(
        KeyConditionExpression="user_id = :u",
        ExpressionAttributeValues={":u": user_id}
    )
    return resp.get("Items", [])

def update_image_status(user_id: str, image_id: str, status: str):
    _image_table().update_item(
        Key={"user_id": user_id, "image_id": image_id},
        UpdateExpression="SET #s = :s, updated_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": status,
            ":t": datetime.utcnow().isoformat()
        }
    )

def update_image_result(user_id: str, image_id: str, **fields):
    expr_names = {"#s": "status"}
    expr_values = {":t": datetime.utcnow().isoformat()}
    updates = ["updated_at = :t"]

    for k, v in fields.items():
        if k == "status":
            updates.append("#s = :s")
            expr_values[":s"] = v
        else:
            updates.append(f"{k} = :{k}")
            expr_values[f":{k}"] = v

    _image_table().update_item(
        Key={"user_id": user_id, "image_id": image_id},
        UpdateExpression="SET " + ", ".join(updates),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values
    )

def add_followup_answer(user_id: str, image_id: str, answer: dict):
    item = get_image_record(user_id, image_id)
    if not item:
        return None

    answers = item.get("followup_answers", [])
    answers.append(answer)

    _image_table().update_item(
        Key={"user_id": user_id, "image_id": image_id},
        UpdateExpression="SET followup_answers = :a, updated_at = :t",
        ExpressionAttributeValues={
            ":a": answers,
            ":t": datetime.utcnow().isoformat()
        }
    )
    item["followup_answers"] = answers
    return item