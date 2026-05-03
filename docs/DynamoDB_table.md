### Users (DYNAMODB_USER_TABLE)

```json
{
  "user_id": "xxx@example.com",        // Partition Key
  "email": "xxx@example.com",
  "password_hash": "...",
  "created_at": "2026-05-02T08:44:56.486718"
}
```

### ImageMetadata (DYNAMODB_IMAGE_TABLE)

```json
{
  "user_id": "xxx@example.com",        // Partition Key
  "image_id": "123",                   // Sort Key

  "s3_key": "xxx@example.com/abc.jpg",
  "status": "uploaded | processing | needs_followup | complete | failed | deleted", 

  "label": "cat",
  "confidence": 0.92,

  "location": {
    "lat": 34.02,
    "lng": -118.28
  },

  "followup_questions": ["Is this your pet?"],
  "followup_answers": ["Yes"],

  "created_at": "2026-05-02T08:44:56.486718",
  "updated_at": "2026-05-02T08:44:56.486718"
}
```

### ZipJobs (DYNAMODB_JOB_TABLE)

```json
{
  "user_id": "xxx@example.com",        // Partition Key
  "job_id": "456",                     // Sort Key

  "type": "zip_upload | download",

  "status": "uploaded | processing | complete | failed",

  "s3_key": "uploads/zips/xxx.zip",  // zip_upload only
  "result_s3_key": "downloads/xxx.zip",  // download only

  "total_files": 10,
  "processed_files": 3,

  "image_ids": ["img1", "img2", "img3", "img4", "img5"],  // download only

  "created_at": "2026-05-02T08:44:56.486718",
  "updated_at": "2026-05-02T08:44:56.486718"
}
```

