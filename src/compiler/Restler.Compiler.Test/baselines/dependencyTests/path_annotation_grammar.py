""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

_stores_post_delivery_metadata = dependencies.DynamicVariable("_stores_post_delivery_metadata")

_stores_post_id = dependencies.DynamicVariable("_stores_post_id")

_stores_post_metadata = dependencies.DynamicVariable("_stores_post_metadata")

def parse_storespost(data):
    """ Automatically generated response parser """
    # Declare response variables
    temp_7262 = None
    temp_8173 = None
    temp_7680 = None
    # Parse the response into json
    try:
        data = json.loads(data)
    except Exception as error:
        raise ResponseParsingException("Exception parsing response, data was not valid json: {}".format(error))

    # Try to extract each dynamic object


    try:
        temp_7262 = str(data["delivery"]["metadata"])
    except Exception as error:
        # This is not an error, since some properties are not always returned
        pass


    try:
        temp_8173 = str(data["id"])
    except Exception as error:
        # This is not an error, since some properties are not always returned
        pass


    try:
        temp_7680 = str(data["metadata"])
    except Exception as error:
        # This is not an error, since some properties are not always returned
        pass


    # If no dynamic objects were extracted, throw.
    if not (temp_7262 or temp_8173 or temp_7680):
        raise ResponseParsingException("Error: all of the expected dynamic objects were not present in the response.")

    # Set dynamic variables
    if temp_7262:
        dependencies.set_variable("_stores_post_delivery_metadata", temp_7262)
    if temp_8173:
        dependencies.set_variable("_stores_post_id", temp_8173)
    if temp_7680:
        dependencies.set_variable("_stores_post_metadata", temp_7680)

req_collection = requests.RequestCollection([])
# Endpoint: /stores, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("stores"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

    {
        'post_send':
        {
            'parser': parse_storespost,
            'dependencies':
            [
                _stores_post_delivery_metadata.writer(),
                _stores_post_id.writer(),
                _stores_post_metadata.writer()
            ]
        }
    },

],
requestId="/stores"
)
req_collection.add_request(request)

# Endpoint: /stores/{storeId}/order, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("stores"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_stores_post_id.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("order"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("""
    "tags":"""),
    primitives.restler_fuzzable_object("{ \"fuzz\": false }"),
    primitives.restler_static_string(""",
    "storeId":"""),
    primitives.restler_fuzzable_int("1"),
    primitives.restler_static_string(""",
    "storeProperties":
        {
            "tags":"""),
    primitives.restler_static_string('"'),
    primitives.restler_static_string(_stores_post_metadata.reader()),
    primitives.restler_static_string(""""
        }
    ,
    "deliveryProperties":
        {
            "tags":"""),
    primitives.restler_fuzzable_object("{ \"fuzz\": false }"),
    primitives.restler_static_string("""
        }
    ,
    "rush":"""),
    primitives.restler_fuzzable_bool("true"),
    primitives.restler_static_string(""",
    "bagType":"""),
    primitives.restler_fuzzable_string("fuzzstring", quoted=True),
    primitives.restler_static_string(""",
    "items":
    [
        {
            "name":"""),
    primitives.restler_fuzzable_string("fuzzstring", quoted=True),
    primitives.restler_static_string(""",
            "deliveryTags":"""),
    primitives.restler_static_string('"'),
    primitives.restler_static_string(_stores_post_delivery_metadata.reader()),
    primitives.restler_static_string("""",
            "code":"""),
    primitives.restler_fuzzable_int("1"),
    primitives.restler_static_string(""",
            "storeId":"""),
    primitives.restler_fuzzable_int("1"),
    primitives.restler_static_string(""",
            "expirationMaxDate":"""),
    primitives.restler_fuzzable_string("fuzzstring", quoted=True),
    primitives.restler_static_string("""
        }
    ],
    "useDoubleBags":"""),
    primitives.restler_fuzzable_bool("true"),
    primitives.restler_static_string(""",
    "bannedBrands":
    [
        """),
    primitives.restler_fuzzable_string("fuzzstring", quoted=True),
    primitives.restler_static_string("""
    ]}"""),
    primitives.restler_static_string("\r\n"),

],
requestId="/stores/{storeId}/order"
)
req_collection.add_request(request)
