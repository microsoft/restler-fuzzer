""" THIS IS AN AUTOMATICALLY GENERATED FILE!"""
from __future__ import print_function
import json
from engine import primitives
from engine.core import requests
from engine.errors import ResponseParsingException
from engine import dependencies
req_collection = requests.RequestCollection([])
# Endpoint: /vm:stop{id}, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("vm:stop"),
    primitives.restler_fuzzable_int("1", examples=["1234"]),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/vm:stop{id}"
)
req_collection.add_request(request)

# Endpoint: /vm/{param}:cancel, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("vm"),
    primitives.restler_static_string("/"),
    primitives.restler_fuzzable_int("1", examples=["1234"]),
    primitives.restler_static_string(":cancel"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/vm/{param}:cancel"
)
req_collection.add_request(request)

# Endpoint: /vm:delete({vmName})/activate, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("vm:delete("),
    primitives.restler_fuzzable_int("1", examples=["1234"]),
    primitives.restler_static_string(")"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("activate"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/vm:delete({vmName})/activate"
)
req_collection.add_request(request)

# Endpoint: /vm/hello{vmId}/start/{startId}goodbye, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("vm"),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("hello"),
    primitives.restler_fuzzable_int("1", examples=["1234"]),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("start"),
    primitives.restler_static_string("/"),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False, examples=["ABCDEF"]),
    primitives.restler_static_string("goodbye"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/vm/hello{vmId}/start/{startId}goodbye"
)
req_collection.add_request(request)

# Endpoint: /vm{vmId}:cancel{startId}/pause, method: Post
request = requests.Request([
    primitives.restler_static_string("POST "),
    primitives.restler_basepath(""),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("vm"),
    primitives.restler_fuzzable_int("1", examples=["1234"]),
    primitives.restler_static_string(":cancel"),
    primitives.restler_fuzzable_string("fuzzstring", quoted=False, examples=["ABCDEF"]),
    primitives.restler_static_string("/"),
    primitives.restler_static_string("pause"),
    primitives.restler_static_string(" HTTP/1.1\r\n"),
    primitives.restler_static_string("Accept: application/json\r\n"),
    primitives.restler_static_string("Host: \r\n"),
    primitives.restler_refreshable_authentication_token("authentication_token_tag"),
    primitives.restler_static_string("\r\n"),

],
requestId="/vm{vmId}:cancel{startId}/pause"
)
req_collection.add_request(request)
