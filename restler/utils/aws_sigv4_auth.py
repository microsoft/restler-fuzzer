import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from urllib.parse import urlparse
import logging 


logging.basicConfig(
    filename="/home/suyash/Downloads/boto.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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
        
        # Convert headers string to dictionary
        headers = {}
        print(f"\nHeaders string: {headers_str}")
        # Get the first line which contains the HTTP method, path and version
        first_line = headers_str.split('\r\n')[0]
        # Extract and encode the path portion
        request_path = first_line.split(' ')[1] if ' ' in first_line else '/'
        
        encoded_path = remove_fragment_from_path(request_path)

        print("Encoded path: ", encoded_path)


        print("\nThe OLD message is: ", message)
        # Modify the original message with encoded path
        message = message.replace(f" {request_path} ", f" {encoded_path} ", 1)

        print("\nThe NEW message is: ", message)

        # Store the encoded path in headers
        headers['Request-Line'] = encoded_path

        for line in headers_str.split('\r\n')[1:]:  # Skip first line (HTTP method line)
            if ': ' in line:
                key, value = line.split(': ', 1)
                headers[key] = value
        print(f"\nHeaders: {headers}")
        # print(f"\nBody: {body}")
        # Call signing function with request components


        # Copy headers to avoid modifying the original
        headers_to_sign = {}        
        # Headers to exclude from signing (typical AWS CLI behavior)
                         
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
        
        print(f"\nheaders to sign are:  {headers_to_sign}")

        logging.debug(f"Headers before signing: {headers_to_sign}")
        
        request_path = headers.get('Request-Line', '/')
        
        full_url = f"{endpoint.rstrip('/')}{request_path}"

        print(f"The full url is, {full_url}")

        # Create request with parsed URL components to maintain encoding
        request = AWSRequest(
            method=method,
            url=full_url,
            data=body,
            headers=headers_to_sign
        )
        
        print(f"\nrequest to sign is: {request}")
        
        logging.debug(f"Created AWSRequest: {request}")

        # Sign the request
        signer = SigV4Auth(credentials, service, region)
        signer.add_auth(request)
        
        # Merge the signed headers back into the original headers
        signed_headers = dict(request.headers)

        logging.debug(f"Signed headers: {signed_headers}")

        print(f"\nsigned AFTER REQUEST headers are:  {signed_headers}")

        for key, value in signed_headers.items():
            headers[key] = value
            
        return headers
    except Exception as e:
        raise Exception(f"Failed to sign request: {str(e)}")