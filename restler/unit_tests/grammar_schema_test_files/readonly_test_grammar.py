""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

_resource_post_id = dependencies.DynamicVariable("_resource_post_id")

def parse_resourcepost(data, **kwargs):
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
        dependencies.set_variable("_resource_post_id", temp_7262)

req_collection = requests.RequestCollection([])
# Endpoint: /resource, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resource"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("Content-Type: "),
    primitives.restler_static_string("application/json"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("""
    "id":"""),
    primitives.restler_fuzzable_string("fuzzstring", quoted=True),
    primitives.restler_static_string(""",
    "person":
        {
            "name":"""),
    primitives.restler_fuzzable_string("fuzzstring", quoted=True),
    primitives.restler_static_string(""",
            "address":"""),
    primitives.restler_fuzzable_object("{ \"fuzz\": false }"),
    primitives.restler_static_string(""",
            "previous_addresses":
            [
                """),
    primitives.restler_fuzzable_string("fuzzstring", quoted=True),
    primitives.restler_static_string("""
            ]
        }
    }"""),
    primitives.restler_static_string("\r\n"),
    
    {

        'post_send':
        {
            'parser': parse_resourcepost,
            'dependencies':
            [
                _resource_post_id.writer()
            ]
        }

    },

],
requestId="/resource"
)
req_collection.add_request(request)

# Endpoint: /resource/{resourceId}, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resource"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resource_post_id.reader(), quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/resource/{resourceId}"
)
req_collection.add_request(request)
