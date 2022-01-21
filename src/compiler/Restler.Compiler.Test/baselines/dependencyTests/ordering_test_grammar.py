""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies

__ordering____services_managementTools = dependencies.DynamicVariable("__ordering____services_managementTools")

__ordering____managementTools_products = dependencies.DynamicVariable("__ordering____managementTools_products")
req_collection = requests.RequestCollection([])
# Endpoint: /products, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath("/api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("products"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

    {

        'pre_send':
        {
            'dependencies':
            [
                __ordering____managementTools_products.reader()
            ]
        }

    },

],
requestId="/products"
)
req_collection.add_request(request)

# Endpoint: /services, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath("/api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("services"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

    {

        'post_send':
        {

            'dependencies':
            [
                __ordering____services_managementTools.writer()
            ]
        }

    },

],
requestId="/services"
)
req_collection.add_request(request)

# Endpoint: /managementTools, method: Get
request = requests.Request([
    primitives.restler_static_string("GET "),
    primitives.restler_basepath("/api"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("managementTools"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: localhost:8888\r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

    {

        'pre_send':
        {
            'dependencies':
            [
                __ordering____services_managementTools.reader()
            ]
        }
,

        'post_send':
        {

            'dependencies':
            [
                __ordering____managementTools_products.writer()
            ]
        }

    },

],
requestId="/managementTools"
)
req_collection.add_request(request)
