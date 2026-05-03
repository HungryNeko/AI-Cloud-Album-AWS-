# AI Cloud Album

**Author**: HungryNeko

AI Cloud Album is a cloud-native, event-driven image management system designed to handle large-scale image storage and processing.

The system integrates REST APIs with AWS services including S3, DynamoDB, SQS, and Lambda to build a fully asynchronous processing pipeline. Machine learning (YOLOv8) is used for automatic image classification, enabling intelligent organization and retrieval of images.

## Major Files and Directories in the Repository

The repository is organized into four main parts: `backend/`, `frontend/`, `lambda/`, `docs/`, and `data/`.

- `backend/` contains the Flask backend application, including the main entry point, API routes, service layer, utility functions, Docker configuration, and backend tests.
- `frontend/` contains the client-side web application, including HTML pages, CSS stylesheets, JavaScript files, and the Leaflet map library used for map visualization.
- `lambda/` contains AWS Lambda functions and related machine learning resources for asynchronous image processing, ZIP handling, and model inference.
- `docs/` contains project documentation such as the API specification, DynamoDB schema notes, and SQS message format.
- `data/` contains test data, image coordinate files, and scripts used for experimentation or data preparation.

## Repository Structure and Organization

The project follows a clear separation of concerns. The backend handles API logic and cloud service integration, the frontend handles user interaction and visualization, Lambda functions handle asynchronous processing, and documentation is stored separately from the source code.

A simplified structure is shown below:

```
.
├── backend/
│   ├── app.py
│   ├── wsgi.py
│   ├── config.py
│   ├── routes/
│   ├── services/
│   ├── utils/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── pages/
│   └── static/
├── lambda/
│   ├── upload/
│   ├── download/
│   ├── class/
│   ├── name/
│   └── test/
├── docs/
└── data/
```

This organization keeps the application modular and makes it easier to develop, test, and deploy each component independently.

## Setup and Deployment

The following instructions describe how to set up and deploy the AI Cloud Album system from scratch.

### 1. Prerequisites

Before running the project, make sure you have:

- Python 3.10 or later
- pip
- Git
- Docker
- An AWS account with access to EC2, S3, SQS, Lambda, and DynamoDB
- A valid EC2 key pair (`.pem` file) for SSH access

### 2. AWS Infrastructure Setup

Before running the application, the following AWS resources must be created:

#### S3 Buckets

- One bucket for **user images and ZIP files**
- One bucket for **frontend static assets**

#### DynamoDB Tables
Create the following tables:

- `Users`
- `ImageMetadata`
- `ZipJobs`

Make sure:

- `user_id` is the partition key
- `image_id` or `job_id` is the sort key

The table names can be customized as long as they match the values used in the environment variables and backend code.

No manual schema migration is required, as DynamoDB is schema-flexible.

#### SQS Queues
Create the following queues:

- image-processing-queue
- zip-upload-queue
- download-queue

Each queue is connected to a specific Lambda function:

- **image-processing-queue → class Lambda** (performs image classification and metadata extraction)
- **zip-upload-queue → upload Lambda** (handles ZIP extraction and generates image processing tasks)
- **download-queue → download Lambda** (handles ZIP creation for selected images)

Set the visibility timeout to **15 minutes** to ensure that long-running tasks can complete without triggering duplicate executions.

#### Lambda Functions

Deploy Lambda functions for the following tasks:

- image classification (`class`)
- ZIP extraction during upload (`upload`)
- ZIP creation for download (`download`)

Each Lambda function should be configured with the required environment variables, including AWS region, S3 bucket name, and DynamoDB table names.

Note that different Lambda functions may require different environment variables depending on their responsibilities.

##### **Deployment**

- The `upload`, `download`, and `test` functions can be directly packaged and uploaded to AWS Lambda using Python 3.14.
- The `class` function requires additional machine learning dependencies (ONNX) and must be packaged separately and uploaded via Amazon S3.

Each Lambda function should be connected to its corresponding SQS queue based on the system workflow.

Each message from SQS triggers exactly one Lambda execution.

##### **Configuration**

- **Timeout**: 15 minutes (to support long-running tasks such as ZIP processing)
- **Memory**: 512 MB

##### IAM Permissions

Lambda execution roles must be configured using IAM to allow access to the required AWS services:

- **Amazon S3**: read and write image and ZIP files  
- **Amazon DynamoDB**: read and update image metadata and job records  
- **Amazon SQS**: receive and delete messages for asynchronous processing  
- **Amazon CloudWatch Logs**: write logs for monitoring and debugging  

These permissions are assigned through IAM roles to ensure secure and controlled access between services.

##### **Notes**

- The `test` Lambda function is used only for development and debugging and is not part of the production workflow.
- The `name` Lambda function was part of the initial design but is not used in the current system.
- Lambda functions are not designed to run locally and require AWS infrastructure.
- Machine learning inference is implemented in the `class` Lambda using an ONNX-based model.

### 3. Environment Configuration

The backend and Lambda functions use **separate environment configurations**.

#### Backend Environment Variables

Create a `.env` file in the `backend/` directory:

```env
SECRET_KEY=your_secret_key
JWT_SECRET=your_jwt_secret

AWS_REGION=us-west-1     # your_region

S3_BUCKET=your_s3_bucket_name

SQS_IMAGE_PROCESSING_URL=your_image_queue_url
SQS_ZIP_UPLOAD_URL=your_zip_upload_queue_url
SQS_DOWNLOAD_URL=your_download_queue_url

DYNAMODB_USER_TABLE=Users           # your_user_table_name
DYNAMODB_IMAGE_TABLE=ImageMetadata  # your_image_table_name
DYNAMODB_JOB_TABLE=ZipJobs          # your_job_table_name
```

Do not commit `.env` or any credential files to the repository.

#### Lambda Environment Variables

Each Lambda function should be configured with only the environment variables it needs. The exact variables may differ by function.

##### Common variables

Some functions may share:

```env
AWS_REGION=us-west-1
S3_BUCKET=your_s3_bucket_name
```

##### Image classification (`class`)

Used for image processing and metadata lookup:

```env
AWS_REGION=us-west-1
S3_BUCKET=your_s3_bucket_name
DYNAMODB_USER_TABLE=Users
DYNAMODB_IMAGE_TABLE=ImageMetadata
LAMBDA_TIME_GUARD_SECONDS=30
```

##### ZIP upload processing (`upload`)

Used for extracting uploaded ZIP files and triggering image processing:

```env
AWS_REGION=us-west-1
S3_BUCKET=your_s3_bucket_name
DYNAMODB_IMAGE_TABLE=ImageMetadata
DYNAMODB_ZIP_JOBS_TABLE=ZipJobs
SQS_IMAGE_PROCESSING_URL=your_image_processing_queue_url
```

##### ZIP download processing (`download`)

Used for packaging selected images into a ZIP file:

```env
AWS_REGION=us-west-1
S3_BUCKET=your_s3_bucket_name
DYNAMODB_IMAGE_TABLE=ImageMetadata
DYNAMODB_ZIP_JOBS_TABLE=ZipJobs
```

##### Test function (`test`)

This function is intended for development or debugging.

```env

```

### 4. External Dependencies

Install backend dependencies:

```bash
cd backend
pip install -r requirements.txt
```

The main backend dependencies include Flask, boto3, PyJWT, gunicorn, flask-cors, Werkzeug, and python-dotenv.

### 5. Running Locally (Requires AWS Resources)

#### Backend

The backend can be run locally for development and debugging:

```bash
cd backend
python app.py
```

If using Gunicorn:

```bash
gunicorn app:app
```

Important:

- The backend connects to AWS services at runtime
- If S3 / DynamoDB / SQS / Lambda are not set up, features will fail
- Local execution is mainly for development, not full standalone usage

#### Frontend

Open the HTML files inside the `frontend/` directory in a browser or serve them using a simple static server.

### 6. AWS Deployment

#### Backend Deployment on EC2

The Flask backend is deployed on an Amazon EC2 instance running Ubuntu 24.04. A typical deployment process is:

```bash
scp -i <key>.pem ai_cloud_album_backend.zip ubuntu@<ec2_public_ip>:~

ssh -i <key>.pem ubuntu@<ec2_public_ip>

unzip ai_cloud_album_backend.zip
cd ai_cloud_album_backend

sudo docker stop backend || true
sudo docker rm backend || true

sudo docker build -t ai-album-backend .
sudo docker run -d -p 80:8000 --name backend --env-file .env ai-album-backend
```

This setup assumes that the Dockerfile exposes the backend application on port `8000` inside the container and maps it to port `80` on the EC2 host.

#### Frontend Deployment

The frontend is deployed using Amazon S3 static website hosting.

Steps:

1. Create an S3 bucket for frontend files

2. Upload all frontend assets (HTML, CSS, JS)

3. Enable 

   Static Website Hosting

   - Index document: `index.html`
   - Error document: `index.html`

4. Disable **Block Public Access**

5. Add the following bucket policy to allow public access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<bucket-name>/*"
    }
  ]
}
```

6. Access the frontend via the S3 website endpoint.

#### Monitoring

Use CloudWatch to:

- view Lambda logs
- debug async processing issues
