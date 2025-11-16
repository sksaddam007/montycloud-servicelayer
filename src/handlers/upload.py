import base64
import json
import os
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser

from .aws_utils import get_client, get_resource

def _extract_boundary(content_type):
    if not content_type or 'multipart/form-data' not in content_type.lower():
        raise ValueError('content-type must be multipart/form-data')
    for param in content_type.split(';'):
        param = param.strip()
        if param.lower().startswith('boundary='):
            boundary = param.split('=', 1)[1].strip()
            if boundary.startswith('"') and boundary.endswith('"'):
                boundary = boundary[1:-1]
            if not boundary:
                break
            return boundary
    raise ValueError('Boundary not found in content-type header')

def _parse_multipart_form(content_type, body):
    boundary = _extract_boundary(content_type)
    mime_headers = (
        f'Content-Type: multipart/form-data; boundary={boundary}\r\n'
        'MIME-Version: 1.0\r\n\r\n'
    ).encode('utf-8')
    parser = BytesParser(policy=policy.default)
    message = parser.parsebytes(mime_headers + body)

    if not message.is_multipart():
        raise ValueError('Invalid multipart/form-data payload')

    fields = {}
    files = {}

    for part in message.iter_parts():
        disposition = part.get('Content-Disposition', '')
        if 'form-data' not in disposition.lower():
            continue
        name = part.get_param('name', header='content-disposition')
        if not name:
            continue
        filename = part.get_param('filename', header='content-disposition')
        payload = part.get_payload(decode=True) or b''
        if filename:
            files[name] = {
                'filename': filename,
                'content': payload,
                'content_type': part.get_content_type()
            }
        else:
            charset = part.get_content_charset() or 'utf-8'
            fields[name] = payload.decode(charset)

    return fields, files

def handler(event, context):
    try:
        table_name = os.environ['DYNAMODB_TABLE']
        bucket_name = os.environ['S3_BUCKET']
        dynamodb = get_resource('dynamodb')
        table = dynamodb.Table(table_name)
        s3 = get_client('s3')

        headers = event.get('headers') or {}
        content_type = headers.get('content-type') or headers.get('Content-Type')
        if not content_type:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing content-type header'})
            }
        
        body = event['body']
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)
        elif isinstance(body, str):
            body = body.encode()
        try:
            form_data, files = _parse_multipart_form(content_type, body)
        except ValueError as parse_error:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': str(parse_error)})
            }

        image_field = files.get('image')
        if not image_field:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Image file missing in form-data'})
            }

        image_content = image_field['content']
        filename = image_field['filename']

        if not image_content or not filename:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Image content or filename not found in form-data'})
            }

        tags_raw = form_data.get('tags', '')
        tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]

        image_id = str(uuid.uuid4())
        s3_key = f"{form_data.get('user_id', 'unknown_user')}/{image_id}-{filename}"

        # Upload image to S3
        s3.put_object(Bucket=bucket_name, Key=s3_key, Body=image_content)
        s3_url = f"s3://{bucket_name}/{s3_key}"

        # Save metadata to DynamoDB
        item = {
            'image_id': image_id,
            'user_id': form_data.get('user_id'),
            'title': form_data.get('title'),
            'description': form_data.get('description'),
            'tags': tags,
            'upload_time': datetime.now(timezone.utc).isoformat(),
            's3_url': s3_url
        }
        table.put_item(Item=item)

        return {
            'statusCode': 200,
            'body': json.dumps({'image_id': image_id})
        }

    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
