Users = {
  "user_id": "xxx@gmail.com",
  "email": "xxx@gmail.com",
  "password_hash": "...",
  "created_at": "time"
}

ImageMetadata = {
  "user_id": "123",        // Partition Key
  "image_id": "abc",       // Sort Key

  "s3_key": "user/abc.jpg",
  "status": "processing",

  "label": "cat",
  "confidence": 0.92,

  "location": {
    "lat": 34.02,
    "lng": -118.28
  },

  "followup_questions": ["Is this your pet?"],
  "followup_answers": ["Yes"],

  "created_at": "...",
  "updated_at": "..."
}

ZipJobs = {
  "user_id": "xxx",    // Partition Key
  "job_id": "xxx",     // Sort Key

  "type": "zip_upload | download",

  "status": "uploaded | processing | complete | failed",

  "s3_key": "uploads/zips/xxx.zip",  // upload only
  "result_s3_key": "downloads/xxx.zip",  // download only

  "total_files": 10,
  "processed_files": 3,

  "image_ids": ["img1", "img2", "img3", "img4", "img5"],  // download only

  "created_at": "...",
  "updated_at": "..."
}