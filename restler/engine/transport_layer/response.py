# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from abc import ABCMeta, abstractmethod, abstractproperty
import string
import re
from typing import Dict, List

import hyper
from restler_settings import Settings

DELIM = "\r\n\r\n"
VALID_CODES = {'200', '201', '202', '204', '304'}
TIMEOUT_CODE = '599'
CONNECTION_CLOSED_CODE = '598'
RESTLER_BUG_CODES = [TIMEOUT_CODE, CONNECTION_CLOSED_CODE]
# Code that RESTler may assign to a request that was never sent to the server.
# This is used as a way to identify that a target request was never sent as part
# of a sequence because the sequence failed prior to that request being reached.
RESTLER_INVALID_CODE = '999'

class AbstractHttpResponse(object, metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, response):
        pass

    @abstractproperty
    def to_str(self):
        pass

    @abstractproperty
    def to_str(self) -> str:
        pass

    @abstractproperty
    def status_code(self) -> str:
        pass

    @abstractproperty
    def body(self) -> str:
        pass

    @abstractproperty
    def headers(self) -> str:
        """Raw response header section of response"""
        pass

    @abstractproperty
    def headers_dict(self) -> Dict:
        pass
 
    @abstractmethod
    def has_valid_code(self) -> bool:
        pass

    @abstractmethod
    def has_bug_code(self) -> bool:
        pass

    @abstractproperty
    def json_body(self) -> str:
        pass

    @abstractproperty
    def status_text(self) -> str:
        pass


class Http2Response(AbstractHttpResponse):
    def __init__(self, response: hyper.HTTP20Response):
        """ Hyper response facade
        """
        self._response = response
        self._body = self._response.read(decode_content=True).decode('utf-8')

    @property
    def to_str(self) -> str:
        #TODO: remove the need for this function.
        # It is hacky.
        return f"{self.headers}{DELIM}{self.body}"

    @property
    def status_code(self) -> str:
        return str(self._response.status)

    @property
    def body(self) -> str:
        return self._body

    @property
    def headers(self) -> str:
        """Raw response header section of response"""
        h_generator = self._response.headers.iter_raw()
        header_str = '\n\r'.join(f"{k.decode('utf-8')}: {v.decode('utf-8')}" for k,v in h_generator)
        return header_str 

    @property
    def headers_dict(self) -> Dict:
        h_dict = dict()
        for k, v  in self._response.headers.iter_raw():
            h_dict[k] = v
        return h_dict
 
    def has_valid_code(self) -> bool:
        sc = self._response.status
        return sc in VALID_CODES

    def has_bug_code(self) -> bool:
        sc = self._response.status
        custom_bug = sc in Settings().custom_non_bug_codes
        fiveXX_code = sc >= 500
        return custom_bug or fiveXX_code

    @property
    def json_body(self) -> str:
        # TODO: actually parse json data
        return self.body

    @property
    def status_text(self) -> str:
        """
        This is not used in HTTP/2, and so is always an empty string.
        """
        return ""


class HttpResponse(AbstractHttpResponse):
    def __init__(self, response_str: str=None):
        """ Initializes an HttpResponse object

        @param response_str: The response that was received from the server

        """
        self._str = None
        self._status_code = None

        if response_str:
            self._str = str(response_str)

            try:
                self._status_code = self._str.split(" ")[1]
            except:
                pass

    @property
    def to_str(self):
        """ Stringifies the whole HttpResponse object.
        This matches the entire response as it was received from the server.

        @return: The entire response as a string
        @rtype: Str

        """
        return self._str

    @property
    def status_code(self):
        """ The status code of the response

        @return: The status code
        @rtype : Str

        """
        return self._status_code

    @property
    def body(self):
        """ The body of the response

        @return: The body
        @rtype : Str

        """
        try:
            return self._str.split(DELIM)[1]
        except:
            return None

    @property
    def headers(self):
        """ The headers of the response

        @return: The headers
        @rtype : List[Str]

        """
        try:
            response_without_body = self._str.split(DELIM)[0]
            # assumed format: HTTP/1.1 STATUS_CODE STATUS TEXT\r\nresponse...
            return response_without_body.split(" ", 2)[2].split('\r\n')[1:]
        except:
            return None

    @property
    def headers_dict(self):
        """ The parsed name-value pairs of the headers of the response
        Headers which are not in the expected format are ignored.

        @return: The headers
        @rtype : Dict[Str, Str]

        """
        headers_dict = {}
        if self.headers is None:
            return headers_dict

        for header in self.headers:
            try:
                payload_start_idx = header.index(":")
                header_name = header[0:payload_start_idx]
                header_val = header[payload_start_idx+1:]
                headers_dict[header_name] = header_val
            except Exception as error:
                print(f"Error parsing header: {header}")
                pass
        return headers_dict

    @property
    def json_body(self):
        """ The json portion of the body if exists.

        @return: The json body
        @rtype : Str or None

        """
        def is_invalid(c):
            """ Returns True if character is an unexpected value.
            This function is called when checking before curly braces in a response.
            Hex values and CRLF characters are considered valid, all others are not.
            """
            return c not in string.hexdigits and c != '\r' and c != '\n' and c != ' '

        try:
            body = self.body
            for idx, c in enumerate(body):
                if c == '{':
                    l_index = idx
                    r_find = '}'
                    break
                elif c == '[':
                    l_index = idx
                    r_find = ']'
                    break
                elif is_invalid(c):
                    return None

            r_index = body.rindex(r_find) + 1
            return body[l_index : r_index]
        except:
            return None

    @property
    def status_text(self):
        """ Returns the status text of the response

        @return: The status text
        @rtype : Str

        """
        try:
            # assumed format: HTTP/1.1 STATUS_CODE STATUS TEXT\r\nresponse...
            return self._str.split(" ", 2)[2].split('\r\n')[0]
        except:
            return None

    def has_bug_code(self):
        """ Returns True if the status code is considered a bug

        @return: True if the status code is considered a bug
        @rtype : Bool

        """
        if self._status_code:
            if Settings().custom_non_bug_codes:
                # All codes except the ones in the custom_non_bug_codes list should be flagged as bugs.
                # Hence, return False only if the status code exists in the list.
                for code in Settings().custom_non_bug_codes:
                    if re.match(code, self._status_code):
                        return False
                else:
                    return True
            if self._status_code.startswith('5'):
                return True
            for code in Settings().custom_bug_codes:
                if re.match(code, self._status_code):
                    return True
        return False

    def has_valid_code(self):
        """ Returns True if the status code is a valid status code

        @return: True if the status code is a valid status code
        @rtype : Bool

        """
        if self._status_code:
            return self._status_code in VALID_CODES
        return False