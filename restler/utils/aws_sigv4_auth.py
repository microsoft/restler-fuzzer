#signer.py

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from urllib.parse import urlparse
import logging 

script_dir = os.path.dirname(os.path.abspath(__file__))
log_file_path = os.path.join(script_dir, "boto.log")

logging.basicConfig(
    filename=log_file_path,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def sign_request(method, headers, body, auth_data):
    try:
        logging.debug("Starting request signing process.")
        # Extract parameters
        service = auth_data.get('service', 's3')
        region = auth_data.get('region', 'default')
        endpoint = auth_data.get('endpoint', '')
        ACCESS_KEY = auth_data.get('access_key')
        SECRET_KEY = auth_data.get('secret_key')

        logging.debug(f"Service: {service}, Region: {region}, Endpoint: {endpoint}")        

        # Create credentials
        credentials = Credentials(
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY
        )
        
        # Copy headers to avoid modifying the original
        headers_to_sign = {}        
        # Headers to exclude from signing (typical AWS CLI behavior)
        exclude_from_signing = [
            'user-agent', 
            'x-restler-sequence-id',
            'Accept',
            'content-length',
            'x-amz-expected-bucket-owner',
            'x-amz-security-token'
        ]                    
        
        include_in_signing = [
            'host',         
            'x-amz-date',
        ]

        headers_to_sign["Host"] = "localhost:8000"

        # Include content hash if not already present
        if 'X-Amz-Content-SHA256' not in headers_to_sign:
            import hashlib
            content_hash = hashlib.sha256(body.encode('utf-8') if isinstance(body, str) else body or b'').hexdigest()
            headers_to_sign['X-Amz-Content-SHA256'] = content_hash
        
        logging.debug(f"Headers before signing: {headers_to_sign}")
        
        request_path = headers.get('Request-Line', '/')
        
        full_url = f"{endpoint.rstrip('/')}{request_path}"

        # Create request with parsed URL components to maintain encoding
        request = AWSRequest(
            method=method,
            url=full_url,
            data=body,
            headers=headers_to_sign
        )
        
        logging.debug(f"Created AWSRequest: {request}")

        # Sign the request
        signer = SigV4Auth(credentials, service, region)
        signer.add_auth(request)
        
        # Merge the signed headers back into the original headers
        signed_headers = dict(request.headers)

        logging.debug(f"Signed headers: {signed_headers}")

        for key, value in signed_headers.items():
            headers[key] = value
            
        return headers
    except Exception as e:
        raise Exception(f"Failed to sign request: {str(e)}")
