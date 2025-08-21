#
# This module is used to sign requests for AWS services using SigV4.
# The `engine_settings.json` file must be configured in the following matter in order to use this signing method.
# The `headers_to_sign` must be modified with respect to your needs.
# Add all the parameters you want to retreive in the `data` dictionary, example is given below
# {
#   "per_resource_settings": {},
#   "max_combinations": 20,  
#   "authentication": {
#       "module": {
#           "name": "utils.aws_sig4_auth",
#           "function": "sign_request",
#           "data": {
#               "access_key": "YOUR_ACCESS_KEY", 
#               "secret_key": "YOUR_SECRET_KEY",
#               "region": "default",
#               "service": "s3",
#               "host": "localhost:8000"
#           },
#           "signing": true
#       }
#   }
# }

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from urllib.parse import urlparse

def remove_fragment_from_path(path):
    """Removes fragment part and merges query parameters correctly"""
    # Split on # first
    if '#' in path:
        base_path, fragment = path.split('#', 1)
        
        # Handle query parameters
        if '?' in fragment:
            fragment_part, fragment_query = fragment.split('?', 1)
            if '?' in base_path:
                # Merge queries with &
                base_path = f"{base_path}&{fragment_query}"
            else:
                # Add query with ?
                base_path = f"{base_path}?{fragment_query}"
        return base_path
    return path

def sign_request(method, message, headers_end, headers_str, body, auth_data):
    try:
        # Extract parameters
        service = auth_data.get('service', 's3')
        region = auth_data.get('region', 'default')
        endpoint = auth_data.get('endpoint', '')
        ACCESS_KEY = auth_data.get('access_key')
        SECRET_KEY = auth_data.get('secret_key')
        host = auth_data.get('host')

        # Create credentials
        credentials = Credentials(
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY
        )
        
        # Convert headers string to dictionary
        headers = {}
        # Get the first line which contains the HTTP method, path and version
        first_line = headers_str.split('\r\n')[0]
        # Extract and encode the path portion
        request_path = first_line.split(' ')[1] if ' ' in first_line else '/'
        
        encoded_path = remove_fragment_from_path(request_path)

        # Modify the original message with encoded path
        message = message.replace(f" {request_path} ", f" {encoded_path} ", 1)
        

        # Store the encoded path in headers
        headers['Request-Line'] = encoded_path

        for line in headers_str.split('\r\n')[1:]:  # Skip first line (HTTP method line)
            if ': ' in line:
                key, value = line.split(': ', 1)
                headers[key] = value

        # Specify the headers to sign
        headers_to_sign = {}        
        
        headers_to_sign["Host"] = host

        # Include content hash if not already present
        if 'X-Amz-Content-SHA256' not in headers_to_sign:
            import hashlib
            content_hash = hashlib.sha256(body.encode('utf-8') if isinstance(body, str) else body or b'').hexdigest()
            headers_to_sign['X-Amz-Content-SHA256'] = content_hash
        
        
        request_path = headers.get('Request-Line', '/')
        
        full_url = f"{endpoint.rstrip('/')}{request_path}"


        # Create request with parsed URL components to maintain encoding
        request = AWSRequest(
            method=method,
            url=full_url,
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