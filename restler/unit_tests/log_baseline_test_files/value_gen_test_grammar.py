# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This grammar was created manually.
# There is no corresponding OpenAPI spec.

from __future__ import print_function
import json

from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

req_collection = requests.RequestCollection([])

_post_a = dependencies.DynamicVariable(
    "_post_a"
)


def parse_A(data, **kwargs):
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
        dependencies.set_variable("_post_a", temp_123)


request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/A/A"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Value-generated: "),
    primitives.restler_fuzzable_string("fuzzstring"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_A,
            'dependencies':
            [
                _post_a.writer()
            ]
        }
    },

],
requestId="/A/{A}"
)
req_collection.add_request(request)


request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload("result"),
    primitives.restler_static_string("/"),
    primitives.restler_fuzzable_number("1.1"),
    primitives.restler_static_string("/A/"),
    primitives.restler_fuzzable_string("fuzzstring"),
    primitives.restler_static_string("/B/"),
    primitives.restler_fuzzable_int("1"),
    primitives.restler_static_string("/C/"),
    primitives.restler_custom_payload("type"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"reader": "'),
    primitives.restler_static_string(_post_a.reader()),
    primitives.restler_static_string('"'),
    primitives.restler_static_string("}"),

],
requestId="/A/{name}/B/{id}/C/{type}"
)
req_collection.add_request(request)

