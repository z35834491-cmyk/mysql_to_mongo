import boto3
from botocore.exceptions import ClientError
# Create client for ap-northeast-1
s3 = boto3.client('s3', region_name='ap-northeast-1')
try:
    s3.list_objects_v2(Bucket='etz-prd-logs', MaxKeys=1)
    print("Success")
except ClientError as e:
    print("Code:", e.response['Error']['Code'])
    print("Headers:", e.response['ResponseMetadata']['HTTPHeaders'])
