# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import string
import re
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

class HttpResponse(object):
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