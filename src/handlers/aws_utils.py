import os

import boto3

def _endpoint_kwargs():
    endpoint = os.environ.get('LOCALSTACK_ENDPOINT_URL')
    return {'endpoint_url': endpoint} if endpoint else {}

def get_resource(service_name):
    return boto3.resource(service_name, **_endpoint_kwargs())

def get_client(service_name):
    return boto3.client(service_name, **_endpoint_kwargs())
