""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

_customer_post_id = dependencies.DynamicVariable("_customer_post_id")

_product_post_id = dependencies.DynamicVariable("_product_post_id")

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
    primitives.restler_fuzzable_string("fuzzstring", quoted=False, examples=["the quick brown fox"]),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("string-date-query-param="),
    primitives.restler_fuzzable_date("2019-06-26", quoted=False, examples=['"2020-12-10"']),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("string-date-time-query-param="),
    primitives.restler_fuzzable_datetime("2019-06-26T20:20:39+00:00", quoted=False, examples=["2022-12-12"]),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("string-password-query-param="),
    primitives.restler_fuzzable_int("1", examples=["2987"]),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("float-number-query-param="),
    primitives.restler_fuzzable_number("1.23", examples=["2.32"]),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("double-number-query-param="),
    primitives.restler_fuzzable_number("1.23", examples=["9.999"]),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("boolean-query-param="),
    primitives.restler_fuzzable_bool("true", examples=["false"]),
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
    primitives.restler_custom_payload("id", quoted=True),
    primitives.restler_static_string(""",
    "Person":
        {
            "int32-body-param":"""),
    primitives.restler_fuzzable_int("1", examples=["321"]),
    primitives.restler_static_string(""",
            "int64-body-param":"""),
    primitives.restler_fuzzable_int("1", examples=["200"]),
    primitives.restler_static_string(""",
            "int-body-param":"""),
    primitives.restler_fuzzable_int("1", examples=["-30"]),
    primitives.restler_static_string(""",
            "obj-body-param":"""),
    primitives.restler_fuzzable_object("{ \"fuzz\": false }", examples=["{\"tags\":{\"label\":\"important\"}}"]),
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
    primitives.restler_fuzzable_group("string-enum-header-param", ['enum_val_1','enum_val_2']  ,quoted=False),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/customer/{customerId}"
)
req_collection.add_request(request)

# Endpoint: /product, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("product"),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("query-producer-param="),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False),
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
    primitives.restler_custom_payload("id", quoted=True, writer=_product_post_id.writer()),
    primitives.restler_static_string(""",
    "info":
        {
            "int32-body-param":"""),
    primitives.restler_fuzzable_int("1", examples=["321"]),
    primitives.restler_static_string(""",
            "int64-body-param":"""),
    primitives.restler_fuzzable_int("1", examples=["200"]),
    primitives.restler_static_string(""",
            "int-body-param":"""),
    primitives.restler_fuzzable_int("1", examples=["-30"]),
    primitives.restler_static_string(""",
            "obj-body-param":"""),
    primitives.restler_fuzzable_object("{ \"fuzz\": false }", examples=["{\"tags\":{\"label\":\"important\"}}"]),
    primitives.restler_static_string("""
        }
    }"""),
    primitives.restler_static_string("\r\n"),
    
    {

        'post_send':
        {
            
            'dependencies':
            [
                _product_post_id.writer()
            ]
        }

    },

],
requestId="/product"
)
req_collection.add_request(request)

# Endpoint: /product/{productId}, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("product"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_product_post_id.reader(), quoted=False),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/product/{productId}"
)
req_collection.add_request(request)
