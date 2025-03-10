import datetime
import hashlib
import hmac
import urllib.parse

def sign(key, msg):
    """Helper function to calculate HMAC-SHA256"""
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def get_signature_key(key, datestamp, region, service):
    """Derives the signing key for AWS SigV4"""
    kDate = sign(f'AWS4{key}'.encode('utf-8'), datestamp)
    kRegion = sign(kDate, region)
    kService = sign(kRegion, service)
    kSigning = sign(kService, 'aws4_request')
    return kSigning

def sign_request(method, headers, body, auth_data):
    """
    Sign an HTTP request using AWS SigV4
    
    Args:
        method: HTTP method (GET, POST, etc)
        headers: Dictionary of request headers
        body: Request body 
        auth_data: Dictionary containing:
            - access_key: AWS access key ID
            - secret_key: AWS secret access key
            - region: AWS region (e.g. us-east-1)
            - service: AWS service (e.g. s3)
            - session_token: Optional AWS session token
    
    Returns:
        Dictionary of headers to add to the request
    """
    # Get required auth parameters
    access_key = auth_data['access_key']
    secret_key = auth_data['secret_key']
    region = auth_data['region']
    service = auth_data['service']
    session_token = auth_data.get('session_token')

    # Create timestamp strings
    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    # Get the canonical URI and query string from headers
    first_line = headers.get('first_line', '')
    url_parts = first_line.split(' ')[1] if first_line else '/'
    url_parsed = urllib.parse.urlparse(url_parts)
    canonical_uri = urllib.parse.quote(url_parsed.path if url_parsed.path else '/')
    canonical_querystring = url_parsed.query if url_parsed.query else ''

    # Create canonical headers
    canonical_headers = {
        'host': headers.get('Host', headers.get('host', '')),
        'x-amz-date': amzdate
    }
    if session_token:
        canonical_headers['x-amz-security-token'] = session_token

    # Sort and format canonical headers
    signed_headers = ';'.join(sorted(canonical_headers.keys()))
    canonical_headers_str = ''.join([f"{k}:{v}\n" for k, v in sorted(canonical_headers.items())])

    # Create payload hash
    payload_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()

    # Create canonical request
    canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n" \
                       f"{canonical_headers_str}\n{signed_headers}\n{payload_hash}"

    # Create string to sign
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = f"{algorithm}\n{amzdate}\n{credential_scope}\n" \
                     f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    # Calculate signature
    signing_key = get_signature_key(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # Create authorization header
    authorization_header = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    # Return headers to be added to the request
    signed_headers_dict = {
        'Authorization': authorization_header,
        'x-amz-date': amzdate,
        'x-amz-content-sha256': payload_hash
    }
    if session_token:
        signed_headers_dict['x-amz-security-token'] = session_token
        
    return signed_headers_dict