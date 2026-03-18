from botocore.exceptions import ClientError
e = ClientError({"Error": {"Code": "PermanentRedirect"}}, "ListObjectsV2")
import botocore
print(isinstance(e, botocore.exceptions.ClientError))
print(e.response.get('Error', {}).get('Code'))
