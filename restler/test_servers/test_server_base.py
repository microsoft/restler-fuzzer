# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Base class used for creating new test servers """
from abc import ABCMeta, abstractmethod
import json

from engine.transport_layer.response import DELIM
from engine.transport_layer.response import HttpResponse

class UnknownRequest(Exception):
    pass

class TestServerBase:
    __test__ = False
    __metaclass__ = ABCMeta

    def __init__(self):
        self._response: HttpResponse = None

    @abstractmethod
    def parse_message(self, message: str):
        pass

    def connect(self):
        pass

    def close(self):
        self._response = None

    @property
    def response(self) -> HttpResponse:
        response = self._response
        self._response = None
        return response

    def _get_response_str(self, status_code: str, description: str="", header: str="Restler Test", body="") -> str:
        try:
            body = json.dumps(body)
        except:
            pass
        return f'HTTP/1.1 {status_code} {description}\r\n{header}{DELIM}{body!s}'

    def _200(self, body: dict) -> HttpResponse:
        response_str = self._get_response_str('200',
                                description='OK',
                                body=body)
        return HttpResponse(response_str)

    def _201(self, body: dict) -> HttpResponse:
        response_str = self._get_response_str('201',
                                description='Created',
                                body=body)
        return HttpResponse(response_str)

    def _202(self, body: dict) -> HttpResponse:
        response_str = self._get_response_str('202',
                                description='Accepted',
                                body=body)
        return HttpResponse(response_str)

    def _400(self, message) -> HttpResponse:
        response_str = self._get_response_str('400',
                                description='Bad Request',
                                body={"error": message})
        return HttpResponse(response_str)

    def _403(self) -> HttpResponse:
        response_str = self._get_response_str('403',
                                description='Forbidden',
                                body={"User not authorized or no auth token specified."})
        return HttpResponse(response_str)

    def _404(self, dyn_object="") -> HttpResponse:
        response_str = self._get_response_str('404',
                                description="Not Found",
                                body={"Resource": dyn_object})
        return HttpResponse(response_str)

    def _405(self, method) -> HttpResponse:
        response_str = self._get_response_str('405',
                               description='Method Not Allowed',
                               body={"error": f"Method, {method}, not supported"})
        return HttpResponse(response_str)

    def _500(self, message="") -> HttpResponse:
        response_str = self._get_response_str('500',
                                description='Internal Server Error',
                                body={"code":"InternalServerError","message":message})
        return HttpResponse(response_str)
