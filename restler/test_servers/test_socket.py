# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Mock TCP socket that forwards requests/responses to/from a test server """
from test_servers.unit_test_server.unit_test_server import *
from engine.transport_layer.response import HttpResponse

class TestSocket(object):
    __test__ = False
    def __init__(self, server_type: str):
        """ Initializes the TestSocket and creates the appropriate test
        server to be used.

        @param server_type: The test server ID that identifies which test
                            server to be used.

        """
        if server_type == 'unit_test':
            self._server = UnitTestServer()
        else:
            err_msg = f"Invalid test server specified: {server_type}"
            print(err_msg)
            raise Exception(err_msg)

    def connect(self, address):
        """ Stub for socket connect.
        Calls the test server's connect function

        @return: None

        """
        self._server.connect()

    def sendall(self, message):
        """ Takes over the responsibilities of a TCP socket's sendall function.
        The caller of this function will "send" its message as though it would a
        regular TCP message. This message will then be forwarded to the appropriate
        test server for parsing.

        @param message: The message that was to be sent to the server
        @type  message: Str

        @return: None

        """
        self._server.parse_message(message)

    def recv(self) -> HttpResponse:
        """ Takes over the responsibilities of a TCP socket's recv function.
        Returns the test server's response.

        @return: The test server's response

        """
        return self._server.response

    def close(self):
        """ Takes over the responsibilities of a TCP socket's close function.
        Calls the test server's close function

        @return: None

        """
        self._server.close()
