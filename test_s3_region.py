import boto3
from botocore.exceptions import ClientError
s3 = boto3.client('s3', region_name='us-east-1')
try:
    # A public bucket or just a bucket that exists in another region
    # aws public datasets
    s3.list_objects_v2(Bucket='arxiv', MaxKeys=1)
except ClientError as e:
    print("Code:", e.response['Error']['Code'])
    print("Headers:", e.response['ResponseMetadata']['HTTPHeaders'])
    print("Region:", e.response['ResponseMetadata']['HTTPHeaders'].get('x-amz-bucket-region'))
