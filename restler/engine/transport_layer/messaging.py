# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Transport layer functionality using Python sockets.

This module handles secure and non-secure socket connections,
message transmission, and response processing.
"""

import ssl
import socket
import time
import threading
from importlib import util
from utils.logging.trace_db import DB as TraceDatabase, SequenceTracker
from utils.formatting import iso_timestamp
from utils.logger import raw_network_logging as RAW_LOGGING
from engine.errors import TransportLayerException
from restler_settings import ConnectionSettings, Settings
from engine.transport_layer.response import HttpResponse

# Constants
DELIM = "\r\n\r\n"
TERMINATING_CHUNK_DELIM = "0\r\n\r\n"
UTF8 = "utf-8"


class HttpSock:
    """
    A class to manage HTTP socket connections, sending requests, and receiving responses.
    Supports SSL/TLS connections and request throttling.
    """

    __last_request_sent_time = time.time()
    __request_sem = threading.Semaphore()

    def __init__(self, connection_settings: ConnectionSettings):
        """
        Initializes an HTTP socket instance.

        :param connection_settings: Configuration for the connection.
        :type connection_settings: ConnectionSettings
        """
        self.connection_settings = connection_settings
        self.ignore_decoding_failures = Settings().ignore_decoding_failures
        self._request_throttle_sec = Settings().request_throttle_ms / 1000.0 if Settings().request_throttle_ms else None
        self._connected = False
        self._sock = None

    def __del__(self):
        """Destructor to ensure socket closure."""
        self._close_socket()

    def set_up_connection(self):
        """Establishes a secure or non-secure connection based on settings."""
        try:
            host = Settings().host
            target_ip = self.connection_settings.target_ip or host
            target_port = self.connection_settings.target_port or (443 if self.connection_settings.use_ssl else 80)

            if Settings().use_test_socket:
                from test_servers.test_socket import TestSocket
                self._sock = TestSocket(Settings().test_server)

            elif self.connection_settings.use_ssl:
                context = ssl._create_unverified_context() if self.connection_settings.disable_cert_validation \
                    else ssl.create_default_context()
                if Settings().client_certificate_path:
                    context.load_cert_chain(
                        certfile=Settings().client_certificate_path,
                        keyfile=Settings().client_certificate_key_path
                    )

                with socket.create_connection((target_ip, target_port)) as sock:
                    self._sock = context.wrap_socket(sock, server_hostname=host)

            else:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.connect((target_ip, target_port))

        except Exception as error:
            raise TransportLayerException(f"Error creating socket: {error}")

    def send_recv(self, message: str, req_timeout_sec: int, reconnect=False):
        """
        Sends an HTTP request and waits for a response.

        :param message: The HTTP request message.
        :param req_timeout_sec: Timeout in seconds for the request.
        :param reconnect: Whether to attempt reconnection on failure.
        :return: Tuple (success flag, response)
        """
        try:
            if reconnect or not self._connected:
                if reconnect and self._sock:
                    self._close_socket()
                self.set_up_connection()
                self._connected = True

            self._send_request(message)
            received_response = self._recv_response(req_timeout_sec)

            if not received_response and not reconnect:
                RAW_LOGGING("Empty response received. Reconnecting...")
                return self.send_recv(message, req_timeout_sec, reconnect=True)

            response = HttpResponse(received_response)
            RAW_LOGGING(f"Received: {response.to_str}")

            if Settings().use_trace_database:
                TraceDatabase().log_request_response(response=response.to_str, timestamp=iso_timestamp())

            return True, response

        except TransportLayerException as error:
            return self._handle_transport_error(error, message, req_timeout_sec, reconnect)

    def _send_request(self, message: str):
        """Encodes and sends an HTTP request over the socket."""
        if "Content-Length: " not in message:
            try:
                body = message.split(DELIM, 1)[1]
                content_length = len(body.encode(UTF8))
                message = message.replace(DELIM, f"\r\nContent-Length: {content_length}{DELIM}", 1)
            except Exception as error:
                RAW_LOGGING(f"Failed to append Content-Length header: {error}")
                raise error

        self._throttle_request()

        try:
            RAW_LOGGING(f"Sending: {message}")
            self._sock.sendall(message.encode(UTF8))
        except Exception as error:
            raise TransportLayerException(f"Error sending data: {error}")
        finally:
            self._release_throttle()

    def _recv_response(self, req_timeout_sec: int) -> str:
        """Receives data from the socket and returns the response."""
        self._sock.settimeout(req_timeout_sec)
        data = ""

        while DELIM not in data:
            try:
                buf = self._sock.recv(2**20)
                if not buf:
                    return data
                data += buf.decode(UTF8, errors="ignore")
            except Exception as error:
                raise TransportLayerException(f"Error receiving data: {error}")

        return data

    def _handle_transport_error(self, error, message, req_timeout_sec, reconnect):
        """Handles connection errors and retries if necessary."""
        response = HttpResponse(str(error))
        RAW_LOGGING(f"Transport Error: {error}")

        if "timed out" in str(error):
            response._status_code = 408  # Request Timeout
        elif self._is_connection_closed(error):
            response._status_code = 499  # Client Closed Request
            if not reconnect:
                return self.send_recv(message, req_timeout_sec, reconnect=True)
        else:
            if not reconnect:
                return self.send_recv(message, req_timeout_sec, reconnect=True)

        return False, response

    def _is_connection_closed(self, error_str):
        """Checks if the error is due to a closed connection."""
        closed_errors = ["[WinError 10054]", "[WinError 10053]", "[Errno 104]"]
        return any(err in str(error_str) for err in closed_errors)

    def _throttle_request(self):
        """Implements request throttling based on settings."""
        if self._request_throttle_sec:
            self.__request_sem.acquire()
            elapsed = time.time() - self.__last_request_sent_time
            if elapsed < self._request_throttle_sec:
                time.sleep(self._request_throttle_sec - elapsed)

    def _release_throttle(self):
        """Releases the request throttle semaphore."""
        if self._request_throttle_sec:
            self.__last_request_sent_time = time.time()
            self.__request_sem.release()

    def _close_socket(self):
        """Closes the socket connection."""
        try:
            if self._sock:
                self._sock.close()
        except Exception as error:
            raise TransportLayerException(f"Error closing socket: {error}")
