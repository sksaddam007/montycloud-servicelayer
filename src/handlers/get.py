import json
import os
from urllib.parse import urlparse

from .aws_utils import get_client, get_resource

def _parse_s3_url(s3_url):
    parsed = urlparse(s3_url)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    if not bucket or not key:
        raise ValueError(f'Invalid s3_url stored for image: {s3_url}')
    return bucket, key

def handler(event, context):
    try:
        table_name = os.environ['DYNAMODB_TABLE']
        dynamodb = get_resource('dynamodb')
        s3 = get_client('s3')
        table = dynamodb.Table(table_name)

        image_id = event['pathParameters']['image_id']

        response = table.get_item(Key={'image_id': image_id})
        item = response.get('Item')

        if not item:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Image not found'})
            }

        bucket_name, key = _parse_s3_url(item['s3_url'])
        
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=3600  # 1 hour
        )

        item['download_url'] = presigned_url

        return {
            'statusCode': 200,
            'body': json.dumps(item)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
