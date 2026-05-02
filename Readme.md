# AI Cloud Album
## Project Structure

### backend
- sources
- docker
- aws-config

### frontend
- sources

### lambda
- sources

### docs
- api-design
- db-design
- ...

### data
- images, a zip file that can directly used to test upload.

## Setup, Environment and deployment 
### frontend  
### backend  
### lambda  
#### Note
- "name" lambda is Not used.  
- "test" lambda is not in running system, just for test other lambda input output and check S3 and Database.
- Unable to running localy.  

#### Upload and Environment  
- "download" and "upload" and "test" can directly copy to AWS lambda, use python 3.14.
- "class" needs to zip and upload to AWS S3 for lambda upload.
#### Deployment
- Connet "Upload", "class", "download" lambda to specified SQSs in AWS accorfing to Back end.  
- Timeout set to 15mines, Memory set to 512M.  
- Each SQS message only triggar exactly ONE lambda.  

## Team Responsibilities

### Frontend + UI Integration
Responsible for developing the HTML and CSS frontend, including user authentication pages, image upload interface, album browsing, map visualization, and dynamic follow-up forms. Also handles frontend-backend integration and status polling for asynchronous tasks.

### Backend + AWS Integration
Responsible for implementing the Flask REST API, user authentication (JWT), image upload handling, and metadata APIs. Integrates backend with AWS services including S3, SQS, DynamoDB, and coordinates communication with Lambda.

### ML + Asynchronous Processing
Responsible for integrating the YOLOv8 model, implementing image classification, metadata extraction (EXIF/location), and follow-up question generation. Also develops Lambda functions to process SQS messages and write results to the database.