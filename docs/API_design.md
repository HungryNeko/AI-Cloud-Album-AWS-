# API Documentation

BASE_URL: http://18.145.174.39

## 1. Conventions

### 1.1 Authentication

All protected endpoints require a Bearer token in the Authorization header:

`Authorization: Bearer <your_token>`

### 1.2 Response Format

Success:

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

Fail:

```json
{
  "success": false,
  "message": "error message"
}
```

### 1.3 Content-Type

- `application/json`: JSON interface
- `multipart/form-data`: File upload interface

## 2. Auth APIs

### 2.1 Register

POST `/api/auth/register`

Request

```json
{
  "email": "user@example.com",
  "password": "123456"
}
```

Response

```json
{
  "success": true,
  "message": "registered",
  "data": {
    "user_id": "user_123",
    "token": "jwt_token_here"
  }
}
```

Error

```json
{
  "success": false,
  "message": "email and password required"
}
```

### 2.2 Login

POST `/api/auth/login`

Request

```json
{
  "email": "user@example.com",
  "password": "123456"
}
```

Response

```json
{
  "success": true,
  "message": "login success",
  "data": {
    "user_id": "user_123",
    "token": "jwt_token_here"
  }
}
```

Error

```json
{
  "success": false,
  "message": "invalid credentials"
}
```

## 3. Image APIs

### 3.1 Upload Single Image

POST `/api/images/upload`

Content-Type: `multipart/form-data`

Form Data: `file`

Response

```json
{
  "success": true,
  "message": "uploaded",
  "data": {
    "image_id": "img_001",
    "status": "processing",
    "s3_key": "user_123/img_001/cat.jpg"
  }
}
```

Error

```json
{
  "success": false,
  "message": "file is required"
}
```

### 3.2 Upload Multiple Images

POST `/api/images/upload-zip`

Content-Type: `multipart/form-data`

Form Data: `file`

Response

```json
{
  "success": true,
  "message": "uploaded",
  "data": {
    "job_id": "job_001",
    "status": "processing",
    "s3_key": "uploads/zips/user_123/job_123.zip"
  }
}
```

Error

```json
{
  "success": false,
  "message": "file is required"
}
```

### 3.3 Image Detail

GET `/api/images/{image_id}`

Response

```json
{
  "success": true,
  "data": {
    "user_id": "user_123",
    "image_id": "img_001",
    "s3_key": "user_123/img_001/cat.jpg",
    "status": "complete",
    "label": "cat",
    "confidence": 0.95,
    "location": {
      "lat": 34.0224,
      "lng": -118.2851
    },
    "followup_questions": [
      "What is the pet name?"
    ],
    "followup_answers": [],
    "created_at": "2026-04-18T10:00:00Z",
    "updated_at": "2026-04-18T10:01:00Z"
  }
}
```

Error

```json
{
  "success": false,
  "message": "image not found"
}
```

### 3.4 Follow-up Questions and ML Output

GET `/api/images/{image_id}/result`

Response

```json
{
  "success": true,
  "data": {
    "image_id": "img_001",
    "status": "needs_followup",
    "label": "dog",
    "followup_questions": [
      "What is the pet name?",
      "When was this photo taken?"
    ]
  }
}
```

Error

```json
{
  "success": false,
  "message": "image not found"
}
```

### 3.5 Submit Follow-up

POST `/api/images/{image_id}/followup`

Request

```json
{
  "pet_name": "Tom",
  "event": "birthday"
}
```

Response

```json
{
  "success": true,
  "message": "followup saved",
  "data": {
    "image_id": "img_001",
    "status": "complete"
  }
}
```

### 3.6 List Images

GET `/api/images`

Response

```json
{
  "success": true,
  "data": [
    {
      "image_id": "img_001",
      "s3_key": "user_123/img_001/cat.jpg",
      "status": "complete",
      "label": "cat",
      "confidence": 0.95
    },
    {
      "image_id": "img_002",
      "s3_key": "user_123/img_002/dog.jpg",
      "status": "processing",
      "label": null,
      "confidence": null
    }
  ]
}
```

### 3.7 Download Selected Images

POST `/api/images/download`

Request

```json
{
  "image_ids": ["img_001", "img_002"]
}
```

Response

```json
{
  "success": true,
  "message": "download job created",
  "data": {
    "job_id": "job_456",
    "status": "processing"
  }
}
```

Error

```json
{
  "success": false,
  "message": "image_ids is required"
}
```

### 3.8 Search Images

GET `/api/images/search`

Query Parameters:

| Parameter | Type   | Required | Description                       |
| --------- | ------ | -------- | --------------------------------- |
| q         | string | optional | Search keywords (space-separated) |

Example Request

```
GET /api/images/search?q=dog
GET /api/images/search?q=dog tom
```

Response

```json
{
  "success": true,
  "data": [
    {
      "image_id": "img_001",
      "label": "dog",
      "s3_key": "user_123/img_001/dog.jpg"
    },
    {
      "image_id": "img_002",
      "label": "dog",
      "s3_key": "user_123/img_002/dog2.jpg"
    }
  ]
}
```

##### No Query

```
GET /api/images/search
```

Returns:

```json
{
  "success": true,
  "data": []
}
```

### 3.9 Delete Image (Soft Delete)

DELETE `/api/images/{image_id}`

Response

```json
{
  "success": true,
  "message": "deleted",
  "data": {
    "image_id": "img_001"
  }
}
```

Error

```json
{
  "success": false,
  "message": "invalid image_id"
}

```

## 4. Job APIs

### 4.1 Get Job

GET `/api/jobs/{job_id}`

Response

```json
{
  "success": true,
  "data": {
    "user_id": "user1@test.com",
    "job_id": "job_123",
    "type": "download",
    "status": "processing",
    "s3_key": null,
    "result_s3_key": null,
    "total_files": 5,
    "processed_files": 2,
    "image_ids": ["img_001", "img_002"],
    "created_at": "2026-04-26T10:00:00Z",
    "updated_at": "2026-04-26T10:01:00Z"
  }
}
```

Error

```json
{
  "success": false,
  "message": "job not found"
}
```

### 4.2 List Jobs

GET `/api/jobs`

Response

```json
{
  "success": true,
  "data": [
    {
      "job_id": "job_123",
      "type": "zip_upload",
      "status": "complete",
      "total_files": 10,
      "processed_files": 10
    },
    {
      "job_id": "job_456",
      "type": "download",
      "status": "processing",
      "total_files": 5,
      "processed_files": 2
    }
  ]
}
```

## 5. Collections & Map

### 5.1 Collections

GET `/api/collections/`

Response

```json
{
  "success": true,
  "data": {
    "by_label": [
      {
        "label": "cat",
        "count": 2,
        "images": [
          {
            "image_id": "img_001",
            "s3_key": "user_123/img_001/cat.jpg"
          }
        ]
      }
    ],
    "by_location": [
      {
        "location": "34.02, -118.28",
        "count": 3,
        "images": [
          {
            "image_id": "img_002",
            "s3_key": "user_123/img_002/dog.jpg"
          }
        ]
      }
    ]
  }
}
```

### 5.2 Map Points

GET `/api/map/points`

Response

```json
{
  "success": true,
  "data": [
    {
      "image_id": "img_001",
      "lat": 34.0224,
      "lng": -118.2851
    },
    {
      "image_id": "img_002",
      "lat": 34.01,
      "lng": -118.28
    }
  ]
}
```

## 6. Utility APIs

### 6.1 Generate Presigned URL

POST `/api/utils/presigned-url`

URL expiration time: 3600s

Request

```json
{
  "s3_key": "user_123/img_001/cat.jpg"
}
```

Response

```json
{
  "success": true,
  "data": {
    "url": "https://signed-url..."
  }
}
```

Error

```json
{
  "success": false,
  "message": "s3_key required"
}
```

## 7. Status Values

The image status uniformly uses the following values:

`uploaded`, `processing`, `needs_followup`, `complete`, `failed`, `deleted`

The ZIP job status uniformly uses the following values:

`uploaded`, `processing`, `complete`, `failed`

## 8. Frontend Flow

##### Upload Process

1. Login and get token
2. `POST /api/images/upload`
3. Repeat `GET /api/images/{image_id}`
4. When `"status" = "needs_followup"`, `GET /api/images/{image_id}/result`
5. Ask user follow-up questions
6. `POST /api/images/{image_id}/followup`
7. Get s3_key `GET /api/images/{image_id}`
7. Get URL `POST /api/utils/presigned-url` to show image

##### Download Process

1. Login and get token
2. Select images
3. `POST /api/images/download`
4. Repeat `GET /api/jobs/{job_id}`
5. When `"status" = "complete"`, get `result_s3_key`
6. Get URL `POST /api/utils/presigned-url` to download zip

## 9. Error Codes

- `400 Bad Request`
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`
- `409 Conflict`
- `413 Payload Too Large`
- `500 Internal Server Error`