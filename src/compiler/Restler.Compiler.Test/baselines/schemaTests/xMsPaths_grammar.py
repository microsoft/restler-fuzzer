""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

__resourceName__type_folder_put_resourceName_path = dependencies.DynamicVariable("__resourceName__type_folder_put_resourceName_path")

__resourceName__type_file_put_resourceName_path = dependencies.DynamicVariable("__resourceName__type_file_put_resourceName_path")
req_collection = requests.RequestCollection([])
# Endpoint: /?operation=list, method: Put
request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("operation=list"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("api-version: "),
    primitives.restler_fuzzable_group("api-version", ['2020-03-01']  ,quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/?operation=list"
)
req_collection.add_request(request)

# Endpoint: /{resourceName}?type=folder, method: Put
request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("resourceName", writer=__resourceName__type_folder_put_resourceName_path.writer(), quoted=False),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("type=folder"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("api-version: "),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False, examples=["2020-03-02"]),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("resource-version: "),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False, examples=["1.2.3.4"]),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    
    {

        'post_send':
        {
            
            'dependencies':
            [
                __resourceName__type_folder_put_resourceName_path.writer()
            ]
        }

    },

],
requestId="/{resourceName}?type=folder"
)
req_collection.add_request(request)

# Endpoint: /{resourceName}?type=file, method: Put
request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("resourceName", writer=__resourceName__type_file_put_resourceName_path.writer(), quoted=False),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("type=file"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("api-version: "),
    primitives.restler_fuzzable_group("api-version", ['2020-03-01']  ,quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("resource-version: "),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    
    {

        'post_send':
        {
            
            'dependencies':
            [
                __resourceName__type_file_put_resourceName_path.writer()
            ]
        }

    },

],
requestId="/{resourceName}?type=file"
)
req_collection.add_request(request)

# Endpoint: /{resourceName}?type=file&operation={operationId}, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(__resourceName__type_file_put_resourceName_path.reader(), quoted=False),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("type=file&operation="),
    primitives.restler_custom_payload("operationId", quoted=False),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("tag="),
    primitives.restler_custom_payload("tag", quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("api-version: "),
    primitives.restler_fuzzable_group("api-version", ['2020-03-01']  ,quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/{resourceName}?type=file&operation={operationId}"
)
req_collection.add_request(request)

# Endpoint: /{resourceName}/{itemName}, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(__resourceName__type_file_put_resourceName_path.reader(), quoted=False),
    primitives.restler_static_string("/"),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("api-version: "),
    primitives.restler_fuzzable_group("api-version", ['2020-03-01']  ,quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/{resourceName}/{itemName}"
)
req_collection.add_request(request)

# Endpoint: /{resourceName}/{itemName}, method: Delete
request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(__resourceName__type_file_put_resourceName_path.reader(), quoted=False),
    primitives.restler_static_string("/"),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("api-version: "),
    primitives.restler_fuzzable_group("api-version", ['2020-03-01']  ,quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/{resourceName}/{itemName}"
)
req_collection.add_request(request)
