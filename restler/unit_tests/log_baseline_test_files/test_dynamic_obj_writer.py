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

req_collection = requests.RequestCollection([])

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("cityName", writer=_city_put_name.writer()),
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
    primitives.restler_fuzzable_int('10000', quoted=True), #, writer=_city_put_population_name.writer()),
    primitives.restler_static_string(', "area": "5000",'),
    primitives.restler_fuzzable_string('strtest', quoted=True),#, writer=_city_put_area_name.writer()),
    primitives.restler_static_string(':'),
    primitives.restler_fuzzable_bool('true', quoted=True),
    primitives.restler_static_string(',"subproperties":'),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"subtest":'),
    primitives.restler_fuzzable_bool("true", quoted=False),#, writer=_city_put_subtest_name.writer()),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'dependencies':
            [
                _city_put_name.writer(),
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


