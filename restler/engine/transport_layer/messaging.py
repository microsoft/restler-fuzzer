# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Transport layer fuctionality using python sockets. """
from __future__ import print_function
import ssl
import socket
import time
import threading
from importlib import util

from utils.logger import raw_network_logging as RAW_LOGGING
from engine.errors import TransportLayerException
from restler_settings import ConnectionSettings
from restler_settings import Settings
from engine.transport_layer.response import *
if util.find_spec("test_servers"):
    from test_servers.test_socket import TestSocket

DELIM = "\r\n\r\n"
UTF8 = 'utf-8'

class HttpSock(object):
    __last_request_sent_time = time.time()
    __request_sem = threading.Semaphore()

    def __init__(self, connection_settings):
        """ Initializes a socket object using low-level python socket objects.

        @param connection_settings: The connection settings for this socket
        @type  connection_settings: ConnectionSettings

        @return: None
        @rtype : None

        """
        self._request_throttle_sec = (float)(Settings().request_throttle_ms/1000.0)\
            if Settings().request_throttle_ms else None

        self.connection_settings = connection_settings

        try:
            self._sock = None
            host = Settings().host
            target_ip = self.connection_settings.target_ip or host
            target_port = self.connection_settings.target_port
            if Settings().use_test_socket:
                self._sock = TestSocket(Settings().test_server)
            elif self.connection_settings.use_ssl:
                if self.connection_settings.disable_cert_validation:
                    context = ssl._create_unverified_context()
                else:
                    context = ssl.create_default_context()
                with socket.create_connection((target_ip, target_port or 443)) as sock:
                    self._sock = context.wrap_socket(sock, server_hostname=host)
            else:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.connect((target_ip, target_port or 80))
        except Exception as error:
            raise TransportLayerException(f"Exception Creating Socket: {error!s}")

    def __del__(self):
        """ Destructor - Closes socket

        """
        if self._sock:
            self._closeSocket()

    def sendRecv(self, message, req_timeout_sec=600):
        """ Sends a specified request to the server and waits for a response

        @param message: Message to be sent.
        @type message : Str
        @param req_timeout_sec: The time, in seconds, to wait for request to complete
        @type req_timeout_sec : Int

        @return:
            False if failure, True if success
            Response if True returned, Error if False returned
        @rtype : Tuple (Bool, String)

        """
        try:
            self._sendRequest(message)
            if not Settings().use_test_socket:
                response = HttpResponse(self._recvResponse(req_timeout_sec))
            else:
                response = self._sock.recv()
            RAW_LOGGING(f'Received: {response.to_str!r}\n')
            return (True, response)
        except TransportLayerException as error:
            response = HttpResponse(str(error).strip('"\''))
            if 'timed out' in str(error):
                response._status_code = TIMEOUT_CODE
                RAW_LOGGING(f"Reached max req_timeout_sec of {req_timeout_sec}.")
            elif self._contains_connection_closed(str(error)):
                response._status_code = CONNECTION_CLOSED_CODE
                RAW_LOGGING(f"{error!s}")
            return (False, response)
        finally:
            self._closeSocket()

    def _contains_connection_closed(self, error_str):
        """ Returns whether or not the error string contains a connection closed error

        @param error_str: The error string to check for connection closed error
        @type  error_str: Str

        @return: True if the error string contains the connection closed error
        @rtype : Bool

        """
        # WinError 10054 occurs when the server terminates the connection and RESTler
        # is being run from a Windows system.
        # Errno 104 occurs when the server terminates the connection and RESTler
        # is being run from a Linux system.
        return '[WinError 10054]' in error_str or '[Errno 104]' in error_str

    def _sendRequest(self, message):
        """ Sends message via current instance of socket object.

        @param message: Message to be sent.
        @type message : Str

        @return: None
        @rtype : None

        """
        def _get_end_of_header(message):
            return message.index(DELIM)

        def _get_start_of_body(message):
            return _get_end_of_header(message) + len(DELIM)

        def _append_to_header(message, content):
            header = message[:_get_end_of_header(message)] + "\r\n" + content + DELIM
            return header + message[_get_start_of_body(message):]

        if "Content-Length: " not in message:
            contentlen = len(message[_get_start_of_body(message):])
            message = _append_to_header(message, f"Content-Length: {contentlen}")
        if self.connection_settings.include_user_agent:
            message = _append_to_header(message, f"User-Agent: restler/{Settings().version}")

        # Attempt to throttle the request if necessary
        self._begin_throttle_request()

        try:
            RAW_LOGGING(f'Sending: {message!r}\n')
            self._sock.sendall(message.encode(UTF8))
        except Exception as error:
            raise TransportLayerException(f"Exception Sending Data: {error!s}")
        finally:
            self._end_throttle_request()

    def _begin_throttle_request(self):
        """ Will attempt to throttle a request by comparing the last time
        a request was sent to the throttle time (if any).

        @return: None
        @rtype : None

        """
        if self._request_throttle_sec:
            HttpSock.__request_sem.acquire()
            elapsed = time.time() - HttpSock.__last_request_sent_time
            throttle_time_remaining = self._request_throttle_sec - elapsed
            if throttle_time_remaining > 0:
                time.sleep(throttle_time_remaining)

    def _end_throttle_request(self):
        """ Will release the throttle lock (if held), so another
        request can be sent.

        Sets last_request_sent_time

        @return: None
        @rtype : None

        """
        if self._request_throttle_sec:
            HttpSock.__last_request_sent_time = time.time()
            HttpSock.__request_sem.release()

    def _recvResponse(self, req_timeout_sec):
        """ Reads data from socket object.

        @param req_timeout_sec: The time, in seconds, to wait for request to complete
        @type req_timeout_sec : Int

        @return: Data received on current socket.
        @rtype : Str

        """
        global DELIM
        data = ''

        # get the data of header (and maybe more)
        bytes_received = 0
        while DELIM not in data:
            try:
                self._sock.settimeout(req_timeout_sec)
                buf = self._sock.recv(2**20)
                bytes_received += len(buf)
            except Exception as error:
                raise TransportLayerException(f"Exception: {error!s}")

            if len(buf) == 0:
                return data

            data += buf.decode(UTF8)

        # Handle chunk encoding
        chuncked_encoding = False
        if 'Transfer-Encoding: chunked\r\n' in data or\
            'transfer-encoding: chunked\r\n' in data:
            chuncked_encoding = True
        if chuncked_encoding:
            while True:
                try:
                    buf = self._sock.recv(2**20)
                    bytes_received += len(buf)
                except Exception as error:
                    raise TransportLayerException(f"Exception: {error!s}")

                if len(buf) == 0:
                    return data

                data += buf.decode(UTF8)
                if data.endswith(DELIM):
                    return data

        header_len = data.index(DELIM) + len(DELIM)

        if data[:12] in ["HTTP/1.1 204", "HTTP/1.1 304"]:
            content_len = 0
        else:
            try:
                data_lower = data.lower()
                content_len = data_lower.split("content-length: ")[1]
                content_len = int(content_len.split('\r\n')[0])
            except Exception as error:
                content_len = 2**20

        bytes_remain = content_len - bytes_received + header_len

        # get rest of socket data
        while bytes_remain > 0:
            try:
                buf = self._sock.recv(2**20)
            except Exception as error:
                raise TransportLayerException(f"Exception: {error!s}")

            if len(buf) == 0:
                return data

            bytes_remain -= len(buf)
            data += buf.decode(UTF8)

        return data

    def _closeSocket(self):
        """ Closes open socket object.

        @return: None
        @rtype : None

        """
        try:
            self._sock.close()
        except Exception as error:
                raise TransportLayerException(f"Exception: {error!s}")
