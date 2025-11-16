import json
import os
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

from .aws_utils import get_resource

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def handler(event, context):
    try:
        table_name = os.environ['DYNAMODB_TABLE']
        dynamodb = get_resource('dynamodb')
        table = dynamodb.Table(table_name)

        params = event.get('queryStringParameters') or {}
        user_id = params.get('user_id')
        tag = params.get('tag')
        date_range = params.get('date_range')

        scan_kwargs = {}
        filter_conditions = []

        if user_id:
            filter_conditions.append(Attr('user_id').eq(user_id))
        
        if tag:
            filter_conditions.append(Attr('tags').contains(tag))

        if date_range:
            try:
                start_date, end_date = [value.strip() for value in date_range.split(',')]
            except ValueError:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'date_range must be in format start,end'})
                }
            filter_conditions.append(Attr('upload_time').between(start_date, end_date))

        if filter_conditions:
            filter_expression = filter_conditions[0]
            for condition in filter_conditions[1:]:
                filter_expression = filter_expression & condition
            scan_kwargs['FilterExpression'] = filter_expression

        response = table.scan(**scan_kwargs)
        
        return {
            'statusCode': 200,
            'body': json.dumps(response['Items'], cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
