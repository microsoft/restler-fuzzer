""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

_app__appId__put_id = dependencies.DynamicVariable("_app__appId__put_id")

__ordering____app__appId__data_deletedApps__appId = dependencies.DynamicVariable("__ordering____app__appId__data_deletedApps__appId")

def parse_appappIdput(data, **kwargs):
    """ Automatically generated response parser """
    # Declare response variables
    temp_7262 = None

    if 'headers' in kwargs:
        headers = kwargs['headers']


    # Parse body if needed
    if data:

        try:
            data = json.loads(data)
        except Exception as error:
            raise ResponseParsingException("Exception parsing response, data was not valid json: {}".format(error))
        pass

    # Try to extract each dynamic object

        try:
            temp_7262 = str(data["id"])
            
        except Exception as error:
            # This is not an error, since some properties are not always returned
            pass



    # If no dynamic objects were extracted, throw.
    if not (temp_7262):
        raise ResponseParsingException("Error: all of the expected dynamic objects were not present in the response.")

    # Set dynamic variables
    if temp_7262:
        dependencies.set_variable("_app__appId__put_id", temp_7262)

req_collection = requests.RequestCollection([])
# Endpoint: /app/{appId}, method: Put
request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_basepath("/api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("app"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("appId", quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    
    {

        'post_send':
        {
            'parser': parse_appappIdput,
            'dependencies':
            [
                _app__appId__put_id.writer()
            ]
        }

    },

],
requestId="/app/{appId}"
)
req_collection.add_request(request)

# Endpoint: /app/{appId}, method: Delete
request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_basepath("/api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("app"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_app__appId__put_id.reader(), quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    
    {

        'post_send':
        {
            
            'dependencies':
            [
                __ordering____app__appId__data_deletedApps__appId.writer()
            ]
        }

    },

],
requestId="/app/{appId}"
)
req_collection.add_request(request)

# Endpoint: /data/deletedApps/{appId}, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath("/api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("data"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("deletedApps"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_app__appId__put_id.reader(), quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    
    {

        'pre_send':
        {
            'dependencies':
            [
                __ordering____app__appId__data_deletedApps__appId.reader()
            ]
        }

    },

],
requestId="/data/deletedApps/{appId}"
)
req_collection.add_request(request)
