# Cloud Image Upload and Management Service

This project is a scalable cloud-native image upload and management service, similar in functionality to the image management layer of Instagram. The service enables users to upload, store, retrieve, list, and delete images.

## Prerequisites

*   Docker
*   Docker Compose
*   AWS CLI
*   AWS SAM CLI
*   Python 3.9
*   pip

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Start the local development environment:**
    This will start LocalStack with S3, DynamoDB, Lambda, and API Gateway services. The `init-aws.sh` script will create the S3 bucket and DynamoDB table.
    ```bash
    docker-compose up -d
    ```

4.  **Configure your shell to talk to LocalStack:**
    ```bash
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
    export AWS_DEFAULT_REGION=us-east-1
    export LOCALSTACK_ENDPOINT_URL=http://localhost:4566
    ```
    These variables ensure both the SAM CLI and the Lambda code itself route to the emulated AWS services rather than the real cloud.

5.  **Deploy the service locally:**
    This command will build the Lambda functions and deploy the CloudFormation stack to LocalStack.
    ```bash
    sam build
    sam deploy --guided
    ```
    When prompted, enter the following:
    - **Stack Name:** `monty-cloud-image-service`
    - **AWS Region:** `us-east-1`
    - **Parameter AWS::Region:** `us-east-1`
    - **Confirm changes before deploy:** `y`
    - **Allow SAM CLI IAM role creation:** `y`
    - **Save arguments to samconfig.toml:** `y`

## Running the Tests

To run the unit tests, execute the following command:
```bash
pytest
```

## API Endpoints

The base URL for the API will be provided in the output of the `sam deploy` command.

*   **POST /images/upload**
    Uploads an image. The request body should be a `multipart/form-data` with the following fields:
    - `image`: The image file.
    - `user_id`: The ID of the user uploading the image.
    - `title`: The title of the image.
    - `description`: A description of the image.
    - `tags`: Comma-separated tags.

*   **GET /images**
    Lists images. Supports the following query parameters for filtering:
    - `user_id`
    - `tag`
    - `date_range` (e.g., `2023-01-01,2023-01-31`)

*   **GET /images/{image_id}**
    Retrieves metadata and a presigned S3 URL for an image.

*   **DELETE /images/{image_id}**
    Deletes an image and its metadata.
