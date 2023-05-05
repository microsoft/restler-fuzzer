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

_post_large_resource = dependencies.DynamicVariable(
    "_post_large_resource"
)


def parse_LR(data, **kwargs):
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
        dependencies.set_variable("_post_large_resource", temp_123)


request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/large-resource/"),
    primitives.restler_custom_payload("obj-id", writer=_post_large_resource.writer()),
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
                _post_large_resource.writer()
            ]
        }
    },

],
requestId="/large-resource/{obj-id}"
)
req_collection.add_request(request)


request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/large-resource/"),
    primitives.restler_static_string(_post_large_resource.reader()),
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

            ]
        }
    },

],
requestId="/large-resource/{obj-id}"
)
req_collection.add_request(request)
