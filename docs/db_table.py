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