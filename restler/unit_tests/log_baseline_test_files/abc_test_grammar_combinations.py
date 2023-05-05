# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This grammar was created manually.
# There is no corresponding OpenAPI spec.
# This grammar is identical to abc_test_grammar.py, except
# additional fuzzable groups are introduced so each request type
# has multiple combinations.
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

_post_d = dependencies.DynamicVariable(
    "_post_d"
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

def parse_B(data, **kwargs):
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


def parse_D(data, **kwargs):
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
    primitives.restler_static_string("/A/A"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
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
    primitives.restler_static_string("Extra-Header: "),
    primitives.restler_fuzzable_group("Extra-Header", ["Header1", "Header2"]),
    primitives.restler_static_string("\r\n"),
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


request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/D/D"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_static_string("Extra-Header: "),
    primitives.restler_fuzzable_group("Extra-Header", ["Header1", "Header2"]),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"A": "'),
    primitives.restler_static_string(_post_a.reader()),
    primitives.restler_static_string('", "B": "'),
    primitives.restler_static_string(_post_b.reader()),
    primitives.restler_static_string('"'),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_D,
            'dependencies':
            [
                _post_d.writer()
            ]
        }
    },

],
requestId="/D/{D}"
)
req_collection.add_request(request)


request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/E"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_static_string("Extra-Header: "),
    primitives.restler_fuzzable_group("Extra-Header", ["Header1", "Header2"]),
    primitives.restler_static_string("\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"D": "'),
    primitives.restler_static_string(_post_d.reader()),
    primitives.restler_static_string('"'),
    primitives.restler_static_string("}"),
],
requestId="/E"
)
req_collection.add_request(request)


