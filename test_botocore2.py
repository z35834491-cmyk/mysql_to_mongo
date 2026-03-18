import botocore.exceptions
class FakeResponse:
    pass
e = botocore.exceptions.ClientError({"Error": {"Code": "PermanentRedirect"}}, "ListObjectsV2")
print(isinstance(e, botocore.exceptions.ClientError))
