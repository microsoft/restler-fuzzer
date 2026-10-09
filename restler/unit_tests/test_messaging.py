# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
import unittest.mock
import engine.dependencies
from restler_settings import ConnectionSettings, Settings, RestlerSettings
from engine.transport_layer.messaging import HttpSock, UTF8
from engine.errors import TransportLayerException
from engine.transport_layer.response import HttpResponse

class MockSocket(object):
    def __init__(self, buffers):
        self.buffers = list(buffers)

    def settimeout(self, timeout):
        pass

    def recv(self, bufsize=2**20):
        if self.buffers:
            return self.buffers.pop(0)
        return b""

    def close(self):
        pass


class MessagingDecodeTest(unittest.TestCase):
    def setUp(self):
        RestlerSettings.TEST_DeleteInstance()
        self.raw_logging_patcher = unittest.mock.patch("engine.transport_layer.messaging.RAW_LOGGING")
        self.raw_logging_patcher.start()
        self.settings = RestlerSettings({})
        self.conn_settings = ConnectionSettings("localhost", 8888)

    def tearDown(self):
        self.raw_logging_patcher.stop()
        RestlerSettings.TEST_DeleteInstance()

    def test_recv_response_binary_body_in_single_buffer(self):
        """ Tests that an HTTP 200 response with binary body in the first recv buffer
        (e.g., zip or octet-stream file download) decodes successfully without raising
        UnicodeDecodeError (Issue #976).
        """
        http_sock = HttpSock(self.conn_settings)
        # Headers followed by binary byte sequence that is invalid UTF-8
        raw_response = b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: 4\r\n\r\n\xfa\xfb\xfc\xfd"
        http_sock._sock = MockSocket([raw_response])

        received = http_sock._recvResponse(10, "GET")
        response = HttpResponse(received)
        self.assertEqual("200", response.status_code)
        self.assertIsNotNone(response.body)

    def test_recv_response_binary_body_in_subsequent_buffer(self):
        """ Tests that an HTTP 200 response where the binary body is received
        in a second recv call decodes successfully without crashing.
        """
        http_sock = HttpSock(self.conn_settings)
        header_buf = b"HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nContent-Length: 4\r\n\r\n"
        body_buf = b"\xfa\xfb\xfc\xfd"
        http_sock._sock = MockSocket([header_buf, body_buf])

        received = http_sock._recvResponse(10, "GET")
        response = HttpResponse(received)
        self.assertEqual("200", response.status_code)
        self.assertIsNotNone(response.body)

    def test_recv_response_invalid_header_raises_transport_layer_exception(self):
        """ Tests that invalid UTF-8 in headers when ignore_decoding_failures is False
        raises TransportLayerException (handled by sendRecv) instead of unhandled UnicodeDecodeError.
        """
        http_sock = HttpSock(self.conn_settings)
        raw_header = b"HTTP/1.1 200 \xfa\xfb\r\n"
        http_sock._sock = MockSocket([raw_header])

        with self.assertRaises(TransportLayerException):
            http_sock._recvResponse(10, "GET")

    def test_recv_response_ignore_decoding_failures_setting(self):
        """ Tests that ignore_decoding_failures=True continues to ignore decoding errors. """
        RestlerSettings.TEST_DeleteInstance()
        settings = RestlerSettings({"ignore_decoding_failures": True})
        conn_settings = ConnectionSettings("localhost", 8888)
        http_sock = HttpSock(conn_settings)

        raw_header = b"HTTP/1.1 200 \xfa\xfb\r\nContent-Length: 0\r\n\r\n"
        http_sock._sock = MockSocket([raw_header])

        received = http_sock._recvResponse(10, "GET")
        response = HttpResponse(received)
        self.assertEqual("200", response.status_code)
