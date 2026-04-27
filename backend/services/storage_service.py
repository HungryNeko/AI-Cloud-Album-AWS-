from services.aws_clients import s3_client
from flask import current_app

URL_ExpiresIn = 3600 # 1 hour

def upload_file_to_s3(file_obj, s3_key: str):
    s3 = s3_client()
    s3.upload_fileobj(
        Fileobj=file_obj,
        Bucket=current_app.config["S3_BUCKET"],
        Key=s3_key
    )
    return {
        "bucket": current_app.config["S3_BUCKET"],
        "key": s3_key
    }

def generate_presigned(s3_key: str):
    s3 = s3_client()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": current_app.config["S3_BUCKET"],
                "Key": s3_key
            },
            ExpiresIn = URL_ExpiresIn
        )

        return {"ok": True, "url": url}

    except Exception as e:
        return {"ok": False, "message": str(e)}