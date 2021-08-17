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

_post_a = dependencies.DynamicVariable(
    "_post_a"
)

_post_b = dependencies.DynamicVariable(
    "_post_b"
)

def parse_A(data):
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

def parse_B(data):
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
        dependencies.set_variable("_post_b", temp_123)


def parse_D(data):
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
        dependencies.set_variable("_post_d", temp_123)


req_collection = requests.RequestCollection([])

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/A/"),
    primitives.restler_custom_payload_uuid4_suffix("postA", writer=_post_a.writer()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
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
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/B/B"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_B,
            'dependencies':
            [
                _post_b.writer()
            ]
        }
    },
],
requestId="/B/{B}"
)
req_collection.add_request(request)


request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/C"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"A": "'),
    primitives.restler_static_string(_post_a.reader()),
    primitives.restler_static_string('", "B": "'),
    primitives.restler_static_string(_post_b.reader()),
    primitives.restler_static_string('"'),
    primitives.restler_static_string("}"),
],
requestId="/C"
)
req_collection.add_request(request)


