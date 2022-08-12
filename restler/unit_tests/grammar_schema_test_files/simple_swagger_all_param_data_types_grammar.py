""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

_customer_post_id = dependencies.DynamicVariable("_customer_post_id")

def parse_customerpost(data, **kwargs):
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
        dependencies.set_variable("_customer_post_id", temp_7262)

req_collection = requests.RequestCollection([])
# Endpoint: /customer, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("customer"),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("string-query-param="),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("string-date-query-param="),
    primitives.restler_fuzzable_date("2019-06-26", quoted=False),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("string-date-time-query-param="),
    primitives.restler_fuzzable_datetime("2019-06-26T20:20:39+00:00", quoted=False),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("string-password-query-param="),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("float-number-query-param="),
    primitives.restler_fuzzable_number("1.23"),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("double-number-query-param="),
    primitives.restler_fuzzable_number("1.23"),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("boolean-query-param="),
    primitives.restler_fuzzable_bool("true"),
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
    "Person":
        {
            "int32-body-param":"""),
    primitives.restler_fuzzable_int("1"),
    primitives.restler_static_string(""",
            "int64-body-param":"""),
    primitives.restler_fuzzable_int("1"),
    primitives.restler_static_string(""",
            "int-body-param":"""),
    primitives.restler_fuzzable_int("1"),
    primitives.restler_static_string(""",
            "obj-body-param":"""),
    primitives.restler_fuzzable_object("{ \"fuzz\": false }"),
    primitives.restler_static_string(""",
            "string-enum-body-param":"""),
    primitives.restler_fuzzable_group("string-enum-body-param", ['enum_body_val_1','enum_body_val_2']  ,quoted=True),
    primitives.restler_static_string(""",
            "int-enum-body-param":"""),
    primitives.restler_fuzzable_group("int-enum-body-param", ['1024','512']  ,quoted=False),
    primitives.restler_static_string(""",
            "string-enum-null-body-param":"""),
    primitives.restler_fuzzable_group("string-enum-null-body-param", ['A','B']  ,quoted=True),
    primitives.restler_static_string("""
        }
    }"""),
    primitives.restler_static_string("\r\n"),
    
    {

        'post_send':
        {
            'parser': parse_customerpost,
            'dependencies':
            [
                _customer_post_id.writer()
            ]
        }

    },

],
requestId="/customer"
)
req_collection.add_request(request)

# Endpoint: /customer/{customerId}, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("customer"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_customer_post_id.reader(), quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_static_string("string-enum-header-param: "),
    primitives.restler_fuzzable_group("string-enum-header-param", ['enum_header_val_1','enum_header_val_2']  ,quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/customer/{customerId}"
)
req_collection.add_request(request)
