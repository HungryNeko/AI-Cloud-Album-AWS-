# AI Cloud Album
## Project Structure

### backend
- sources
- docker
- aws-config

### frontend
- sources
- docker

### lambda
- sources
- docker

### docs
- api-design
- db-design
- ...

### data
- images
- database

## Team Responsibilities

### Frontend + UI Integration
Responsible for developing the HTML and CSS frontend, including user authentication pages, image upload interface, album browsing, map visualization, and dynamic follow-up forms. Also handles frontend-backend integration and status polling for asynchronous tasks.

### Backend + AWS Integration
Responsible for implementing the Flask REST API, user authentication (JWT), image upload handling, and metadata APIs. Integrates backend with AWS services including S3, SQS, DynamoDB, and coordinates communication with Lambda.

### ML + Asynchronous Processing
Responsible for integrating the YOLOv8 model, implementing image classification, metadata extraction (EXIF/location), and follow-up question generation. Also develops Lambda functions to process SQS messages and write results to the database.