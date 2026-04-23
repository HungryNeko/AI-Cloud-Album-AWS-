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

Query Params (optional): `status`, `label`, `location`, `page`, `limit`

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

## 4. Collections & Map

### 4.1 Collections

GET `/api/collections/`

### 4.2 Map Points

GET `/api/map/points`

## 5. Batch Upload & Download

### 5.1 Upload ZIP

POST `/api/images/upload-zip`

### 5.2 Download Selected Images

POST `/api/images/download`

## 6. Status Values

The image status uniformly uses the following values:

`uploaded`, `processing`, `needs_followup`, `complete`, `failed`

## 7. Frontend Flow

##### Upload Process

1. login and get token
2. `POST /api/images/upload`
3. Repeat `GET /api/images/{image_id}`
4. When `"status" = "needs_followup"`, `GET /api/images/{image_id}/result`
5. Ask user follow-up questions
6. `POST /api/images/{image_id}/followup`
7. `GET /api/images/{image_id}`

## 8. Error Codes

- `400 Bad Request`
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`
- `409 Conflict`
- `500 Internal Server Error`