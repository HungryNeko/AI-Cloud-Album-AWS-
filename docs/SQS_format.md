### image-processing-queue (SQS_IMAGE_PROCESSING)

```json
[
    {
        "user_id": "xxx@example.com", 
        "image_id": "123", 
        "s3_key": "xxx@example.com/abc.jpg"
    }
]
```

### zip-upload-queue (SQS_ZIP_UPLOAD)

```json
{
    "user_id": "xxx@example.com",
    "job_id": "456",
    "s3_key": "uploads/zips/xxx@example.com/test.zip"
}
```

### download-queue (SQS_DOWNLOAD)

```json
{
    "user_id": "xxx@example.com",
    "job_id": "789",
    "image_ids": ["img1", "img2"]
}
```

