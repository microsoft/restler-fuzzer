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

_city_house_color_put_name = dependencies.DynamicVariable(
    "_city_house_color_put_name"
)

_leakageruletest_put_name = dependencies.DynamicVariable(
    "_leakageruletest_put_name"
)

_useafterfreetest_put_name = dependencies.DynamicVariable(
    "_useafterfreetest_put_name"
)

_resourcehierarchytest_put_name = dependencies.DynamicVariable(
    "_resourcehierarchytest_put_name"
)

_resourcehierarchychild_put_name = dependencies.DynamicVariable(
    "_resourcehierarchychild_put_name"
)

_namespaceruletest_put_name = dependencies.DynamicVariable(
    "_namespaceruletest_put_name"
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

def parse_cityHouseColorNamePut(data):
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
        dependencies.set_variable("_city_house_color_put_name", temp_123)

def parse_leakageruletestNamePut(data):
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
        dependencies.set_variable("_leakageruletest_put_name", temp_123)

def parse_useafterfreetestNamePut(data):
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
        dependencies.set_variable("_useafterfreetest_put_name", temp_123)

def parse_resourcehierarchytestNamePut(data):
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
        dependencies.set_variable("_resourcehierarchytest_put_name", temp_123)

def parse_resourcehierarchychildNamePut(data):
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
        dependencies.set_variable("_resourcehierarchychild_put_name", temp_123)

def parse_namespaceruletestNamePut(data):
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
        dependencies.set_variable("_namespaceruletest_put_name", temp_123)

req_collection = requests.RequestCollection([])
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
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
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
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
    primitives.restler_static_string("{"),
    primitives.restler_static_string("}"),
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

# This request is intentionally malformed to create a 500 error;
# The body will be sent as {{ instead of {}, which will create an unhandled
# exception when the unit test server attempts to convert the body to valid json
request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
	primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("house"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_house_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("color"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("colorName"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    # Start of malformed body
    primitives.restler_static_string("{"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("}"),
    # End of malformed body
    primitives.restler_static_string("\r\n"),

    {
        'post_send':
        {
            'parser': parse_cityHouseColorNamePut,
            'dependencies':
            [
                _city_house_color_put_name.writer()
            ]
        }
    },

],
requestId="/city/{cityName}/house/{houseName}/color/{colorName}"
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
    primitives.restler_static_string("/"),
    primitives.restler_static_string("color"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_house_color_put_name.reader()),
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
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/farm"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("item"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/item"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("leakageruletest"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("leakageTest"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),

    {
        'post_send':
        {
            'parser': parse_leakageruletestNamePut,
            'dependencies':
            [
                _leakageruletest_put_name.writer()
            ]
        }
    },

],
requestId="/leakageruletest/{leakageTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("leakageruletest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_leakageruletest_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/leakageruletest/{leakageTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("useafterfreetest"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("useafterfreeTest"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),

    {
        'post_send':
        {
            'parser': parse_useafterfreetestNamePut,
            'dependencies':
            [
                _useafterfreetest_put_name.writer()
            ]
        }
    },

],
requestId="/useafterfreetest/{useafterfreeTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("useafterfreetest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_useafterfreetest_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/useafterfreetest/{useafterfreeTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("useafterfreetest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_useafterfreetest_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/useafterfreetest/{useafterfreeTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchytest"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("resourcehierarchyTest"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),

    {
        'post_send':
        {
            'parser': parse_resourcehierarchytestNamePut,
            'dependencies':
            [
                _resourcehierarchytest_put_name.writer()
            ]
        }
    },

],
requestId="/resourcehierarchytest/{resourcehierarchyTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchytest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resourcehierarchytest_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/resourcehierarchytest/{resourcehierarchyTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchytest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resourcehierarchytest_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/resourcehierarchytest/{resourcehierarchyTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchytest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resourcehierarchytest_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchychild"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("resourcehierarchyChild"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),

    {
        'post_send':
        {
            'parser': parse_resourcehierarchychildNamePut,
            'dependencies':
            [
                _resourcehierarchychild_put_name.writer()
            ]
        }
    },

],
requestId="/resourcehierarchychild/{resourcehierarchyChild}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchytest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resourcehierarchytest_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchychild"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resourcehierarchychild_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/resourcehierarchychild/{resourcehierarchyChild}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchytest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resourcehierarchytest_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("resourcehierarchychild"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_resourcehierarchychild_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/resourcehierarchychild/{resourcehierarchyChild}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("namespaceruletest"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("namespaceruleTest"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),

    {
        'post_send':
        {
            'parser': parse_namespaceruletestNamePut,
            'dependencies':
            [
                _namespaceruletest_put_name.writer()
            ]
        }
    },

],
requestId="/namespaceruletest/{namespaceruleTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("namespaceruletest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_namespaceruletest_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/namespaceruletest/{namespaceruleTest}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("namespaceruletest"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_namespaceruletest_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
	primitives.restler_static_string("\r\n")
],
requestId="/namespaceruletest/{namespaceruleTest}"
)
req_collection.add_request(request)
