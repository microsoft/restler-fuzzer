# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import print_function
import json

from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

_city_put_name = dependencies.DynamicVariable(
    "_city_put_name"
)

_city_house_put_name = dependencies.DynamicVariable(
    "_city_house_put_name"
)

def parse_cityNamePut(data):
    temp_123 = None

    try:

        data = json.loads(data)
    except Exception as error:
        raise ResponseParsingException("Exception parsing response, data was not valid json: {}".format(error))

    try:
        temp_123 = str(data["name"])
    except Exception as error:
        pass

    if temp_123:
        dependencies.set_variable("_city_put_name", temp_123)

def parse_cityHouseNamePut(data):
    temp_123 = None

    try:

        data = json.loads(data)
    except Exception as error:
        raise ResponseParsingException("Exception parsing response, data was not valid json: {}".format(error))

    try:
        temp_123 = str(data["name"])
    except Exception as error:
        pass

    if temp_123:
        dependencies.set_variable("_city_house_put_name", temp_123)

req_collection = requests.RequestCollection([])

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("cityName"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"properties":'),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"population":'),
    primitives.restler_fuzzable_int('10000', quoted=True),
    primitives.restler_static_string(', "area": "5000",'),
    primitives.restler_fuzzable_string('strtest', quoted=True),
    primitives.restler_static_string(':'),
    primitives.restler_fuzzable_bool('true', quoted=True),
    primitives.restler_static_string(',"subproperties":'),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"subtest":'),
    primitives.restler_fuzzable_bool("true", quoted=False),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_cityNamePut,
            'dependencies':
            [
                _city_put_name.writer()
            ]
        }
    },

],
requestId="/city/{cityName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("location="),
    primitives.restler_custom_payload("location"),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("group="),
    primitives.restler_fuzzable_group("fuzzable_group_tag", ['A','BB','CCC']),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("house"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}/house"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("house"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("houseName"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("["),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"house":'),
    primitives.restler_custom_payload_uuid4_suffix("houseName", quoted=True),
    primitives.restler_static_string(',"group":'),
    primitives.restler_fuzzable_group("fuzzable_group_tag", ['A','BB','CCC'], quoted=True),
    primitives.restler_static_string("}"),
    primitives.restler_static_string(","),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"arraytest":'),
    primitives.restler_custom_payload("location", quoted=True),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("]"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_cityHouseNamePut,
            'dependencies':
            [
                _city_house_put_name.writer()
            ]
        }
    },

],
requestId="/city/{cityName}/house/{houseName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("house"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_house_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}/house/{houseName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("house"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_house_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}/house/{houseName}"
)
req_collection.add_request(request)


