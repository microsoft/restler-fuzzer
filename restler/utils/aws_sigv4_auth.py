#signer.py

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from urllib.parse import urlparse

def sign_request(method, headers, body, auth_data):
    try:
        # Extract parameters
        service = auth_data.get('service', 's3')
        region = auth_data.get('region', 'default')
        endpoint = auth_data.get('endpoint', 'http://localhost:8000')
        ACCESS_KEY = auth_data.get('access_key')
        SECRET_KEY = auth_data.get('secret_key')
        
        # Create credentials
        credentials = Credentials(
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY
        )
        
        # Copy headers to avoid modifying the original
        headers_to_sign = headers.copy()
        
        # Headers to exclude from signing (typical AWS CLI behavior)
        exclude_from_signing = [
            'user-agent', 
            'x-restler-sequence-id',
            'Accept',
            'content-length',
            'x-amz-expected-bucket-owner',
            'x-amz-security-token'
        ]
        
        # print(f"\nheaders to sign are:  {headers_to_sign}")
        # Remove headers that shouldn't be signed
        for header in exclude_from_signing:
            if header.lower() in headers_to_sign:
                del headers_to_sign[header.lower()]

        del headers_to_sign["Accept"]
        del headers_to_sign["Content-Length"]
        del headers_to_sign["User-Agent"]
        
        # Include content hash if not already present
        if 'X-Amz-Content-SHA256' not in headers_to_sign:
            import hashlib
            content_hash = hashlib.sha256(body.encode('utf-8') if isinstance(body, str) else body or b'').hexdigest()
            headers_to_sign['X-Amz-Content-SHA256'] = content_hash
        
        # Ensure required headers are present
        if 'Host' not in headers_to_sign:
            parsed_url = urlparse(endpoint)
            headers_to_sign['Host'] = parsed_url.netloc
        
        print(f"\nheaders that are signed are:  {headers_to_sign}")

        # Create the request to sign with filtered headers
        request = AWSRequest(
            method=method,
            url=endpoint,
            data=body,
            headers=headers_to_sign
        )
        
        # Sign the request
        signer = SigV4Auth(credentials, service, region)
        signer.add_auth(request)
        
        # Merge the signed headers back into the original headers
        signed_headers = dict(request.headers)
        for key, value in signed_headers.items():
            headers[key] = value
            
        return headers
    except Exception as e:
        raise Exception(f"Failed to sign request: {str(e)}")