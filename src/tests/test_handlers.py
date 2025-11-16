import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from handlers import delete, get, list as list_handler, upload

def _create_multipart_body():
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="user_id"\r\n\r\n'
        f"test_user\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="title"\r\n\r\n'
        f"test_title\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="description"\r\n\r\n'
        f"test_description\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="tags"\r\n\r\n'
        f"tag1,tag2\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="test.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
        f"fake_image_content\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    return boundary, body

@pytest.fixture
def aws_environment():
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['DYNAMODB_TABLE'] = 'images'
    os.environ['S3_BUCKET'] = 'monty-cloud-images'

    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='images',
            KeySchema=[{'AttributeName': 'image_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'image_id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
        )
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=os.environ['S3_BUCKET'])
        yield {'table': table, 's3': s3}

def test_upload_handler(aws_environment):
    boundary, body = _create_multipart_body()
    event = {
        'body': base64.b64encode(body).decode(),
        'headers': {'content-type': f'multipart/form-data; boundary={boundary}'},
        'isBase64Encoded': True,
    }

    response = upload.handler(event, {})
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'image_id' in body

    stored_item = aws_environment['table'].get_item(Key={'image_id': body['image_id']})
    assert stored_item.get('Item')
    assert stored_item['Item']['tags'] == ['tag1', 'tag2']

    s3_key = f"test_user/{body['image_id']}-test.jpg"
    obj = aws_environment['s3'].get_object(Bucket=os.environ['S3_BUCKET'], Key=s3_key)
    assert obj['ResponseMetadata']['HTTPStatusCode'] == 200

def test_get_handler(aws_environment):
    image_id = "test_image_id"
    s3_key = "test_user/test.jpg"
    aws_environment['s3'].put_object(Bucket=os.environ['S3_BUCKET'], Key=s3_key, Body=b"img")
    aws_environment['table'].put_item(Item={
        'image_id': image_id,
        's3_url': f"s3://{os.environ['S3_BUCKET']}/{s3_key}"
    })

    event = {'pathParameters': {'image_id': image_id}}
    response = get.handler(event, {})
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'download_url' in body
    assert body['image_id'] == image_id

def test_list_handler_supports_filters(aws_environment):
    now = datetime.now(timezone.utc)
    older = now - timedelta(days=1)
    aws_environment['table'].put_item(Item={
        'image_id': '1',
        'user_id': 'user1',
        'tags': ['tag1'],
        'upload_time': older.isoformat()
    })
    aws_environment['table'].put_item(Item={
        'image_id': '2',
        'user_id': 'user2',
        'tags': ['tag2'],
        'upload_time': now.isoformat()
    })

    response = list_handler.handler({}, {})
    assert response['statusCode'] == 200
    assert len(json.loads(response['body'])) == 2

    response = list_handler.handler({'queryStringParameters': {'user_id': 'user1'}}, {})
    assert response['statusCode'] == 200
    items = json.loads(response['body'])
    assert len(items) == 1
    assert items[0]['user_id'] == 'user1'

    response = list_handler.handler({'queryStringParameters': {'tag': 'tag2'}}, {})
    assert response['statusCode'] == 200
    items = json.loads(response['body'])
    assert len(items) == 1
    assert items[0]['image_id'] == '2'

    date_range = f"{older.isoformat()},{now.isoformat()}"
    response = list_handler.handler({'queryStringParameters': {'date_range': date_range}}, {})
    assert response['statusCode'] == 200
    items = json.loads(response['body'])
    assert len(items) == 2

    bad_range_resp = list_handler.handler({'queryStringParameters': {'date_range': 'just-one-date'}}, {})
    assert bad_range_resp['statusCode'] == 400

def test_delete_handler(aws_environment):
    image_id = "test_image_id"
    s3_key = "test_user/test.jpg"
    aws_environment['s3'].put_object(Bucket=os.environ['S3_BUCKET'], Key=s3_key, Body=b"")
    aws_environment['table'].put_item(Item={
        'image_id': image_id,
        's3_url': f's3://{os.environ["S3_BUCKET"]}/{s3_key}'
    })
    
    event = {'pathParameters': {'image_id': image_id}}
    response = delete.handler(event, {})
    assert response['statusCode'] == 200
    
    response = aws_environment['table'].get_item(Key={'image_id': image_id})
    assert 'Item' not in response

    with pytest.raises(ClientError):
        aws_environment['s3'].head_object(Bucket=os.environ['S3_BUCKET'], Key=s3_key)
