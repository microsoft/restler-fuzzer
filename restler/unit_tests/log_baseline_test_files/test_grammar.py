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

_city_road_put_name = dependencies.DynamicVariable(
    "_city_road_put_name"
)

_farm_put_name = dependencies.DynamicVariable(
    "_farm_put_name"
)

_farm_animal_put_name = dependencies.DynamicVariable(
    "_farm_animal_put_name"
)

_item_put_name = dependencies.DynamicVariable(
    "_item_put_name"
)

_group_put_name = dependencies.DynamicVariable(
    "_group_put_name"
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

def parse_cityRoadNamePut(data):
    temp_123 = None

    try:

        data =json.loads(data)
    except Exception as error:
        raise ResponseParsingException("Exception parsing response, data was not valid json: {}".format(error))

    try:
        temp_123 = str(data["name"])
    except Exception as error:
        pass

    if temp_123:
        dependencies.set_variable("_city_road_put_name", temp_123)

def parse_farmNamePut(data):
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
        dependencies.set_variable("_farm_put_name", temp_123)

def parse_farmAnimalNamePut(data):
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
        dependencies.set_variable("_farm_animal_put_name", temp_123)

def parse_itemNamePut(data):
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
        dependencies.set_variable("_item_put_name", temp_123)

def parse_groupNamePut(data):
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
        dependencies.set_variable("_group_put_name", temp_123)


req_collection = requests.RequestCollection([])

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/"
)
req_collection.add_request(request)

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
    primitives.restler_static_string('"population":'),
    primitives.restler_fuzzable_int('10000', quoted=True),
    primitives.restler_static_string(', "area": "5000",'),
    primitives.restler_fuzzable_string('strtest', quoted=True),
    primitives.restler_static_string(':'),
    primitives.restler_fuzzable_bool('true', quoted=True),
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
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"house":'),
    primitives.restler_custom_payload_uuid4_suffix("houseName", quoted=True),
    primitives.restler_static_string(',"group":'),
    primitives.restler_fuzzable_group("fuzzable_group_tag", ['A','BB','CCC'], quoted=True),
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
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}/house/{houseName}/color"
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
requestId="/city/{cityName}/house/{houseName}/color/{colorName}"
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
    primitives.restler_static_string("road"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}/road"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("road"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("roadName"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"testpayload":'),
    primitives.restler_custom_payload("testquote", quoted=True),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_cityRoadNamePut,
            'dependencies':
            [
                _city_road_put_name.writer()
            ]
        }
    },

],
requestId="/city/{cityName}/road/{roadName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("road"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_road_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}/road/{roadName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("city"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("road"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_city_road_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/city/{cityName}/road/{roadName}"
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
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("farmName"),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("location="),
    primitives.restler_custom_payload("location"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('testbool', quoted=True),
    primitives.restler_static_string(':'),
    primitives.restler_fuzzable_bool("testval", quoted=True),
    primitives.restler_static_string(',"location":'),
    primitives.restler_custom_payload("location", quoted=True),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_farmNamePut,
            'dependencies':
            [
                _farm_put_name.writer()
            ]
        }
    },

],
requestId="/farm/{farmName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/farm/{farmName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/farm/{farmName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("animal"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/farm/{farmName}/animal"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("animal"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("animalName"),
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
            'parser': parse_farmAnimalNamePut,
            'dependencies':
            [
                _farm_animal_put_name.writer()
            ]
        }
    },

],
requestId="/farm/{farmName}/animal/{animalName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("animal"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_animal_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/farm/{farmName}/animal/{animalName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("farm"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_put_name.reader()),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("animal"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_farm_animal_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/farm/{farmName}/animal/{animalName}"
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
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("item"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_item_put_name.reader()),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("date="),
    primitives.restler_fuzzable_datetime("2020-1-1"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/item/{itemName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("item"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_item_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/item/{itemName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("item"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("itemName"),
    primitives.restler_static_string("?"),
    primitives.restler_static_string("location="),
    primitives.restler_custom_payload("location"),
    primitives.restler_static_string("&"),
    primitives.restler_static_string("date="),
    primitives.restler_fuzzable_datetime("2020-1-1"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"datetest":'),
    primitives.restler_fuzzable_datetime("2020-1-1", quoted=True),
    primitives.restler_static_string(',"id":'),
    primitives.restler_static_string('"/testparts/'),
    primitives.restler_custom_payload("testcustomparts", quoted=False),
    primitives.restler_static_string('"'),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_itemNamePut,
            'dependencies':
            [
                _item_put_name.writer()
            ]
        }
    },

],
requestId="/item/{itemName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("group"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/group"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("group"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_group_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/group/{groupName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("DELETE "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("group"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string(_group_put_name.reader()),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n")
],
requestId="/group/{groupName}"
)
req_collection.add_request(request)

request = requests.Request([
    primitives.restler_static_string("PUT "),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("group"),
    primitives.restler_static_string("/"),
    primitives.restler_custom_payload_uuid4_suffix("groupName"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: restler.unit.test.server.com\r\n"),
    primitives.restler_static_string("Content-Type: application/json\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),
    primitives.restler_static_string("{"),
    primitives.restler_static_string('"city":"'),
    primitives.restler_static_string(_city_put_name.reader()),
    primitives.restler_static_string('", "item": "'),
    primitives.restler_static_string(_item_put_name.reader()),
    primitives.restler_static_string('"'),
    primitives.restler_static_string("}"),
    primitives.restler_static_string("\r\n"),
    {
        'post_send':
        {
            'parser': parse_groupNamePut,
            'dependencies':
            [
                _group_put_name.writer()
            ]
        }
    },

],
requestId="/group/{groupName}"
)
req_collection.add_request(request)

