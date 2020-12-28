# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Test helper classes created from parsing request strings """
from collections import OrderedDict

from engine.transport_layer.response import DELIM

UNIT_TEST_RESOURCE_IDENTIFIER = '<test!>'

class ParsedRequest:
    """ Created by parsing a request string """
    def __init__(self, request_str: str, ignore_dynamic_objects=False):
        # Extract method from request string
        method_split = request_str.split(' ', 1)
        self.method = method_split[0]

        # Split endpoint from header
        endpoint_split = method_split[1].split(' HTTP', 1)
        # Handle query string if necessary
        self.endpoint = endpoint_split[0].split('?', 1)[0]
        # Some requests being parsed (e.g. from bug_buckets.txt) do not contain the
        # full DELIM value in the logs when the authentication token tag exists
        # in the request. For instances where the DELIM value is not found, try
        # checking for the authentication tag when splitting the body.
        # Ex-no-DELIM: METHOD /end/point HTTP/1.1 Auth_Token_Str{}
        # Ex-DELIM: METHOD /end/point HTTP/1.1 DELIM{}
        Auth_Token_Str = 'authentication_token_tag\r\n'
        delim = DELIM
        if DELIM in endpoint_split[1]:
            pass
        elif Auth_Token_Str in endpoint_split[1]:
            delim = Auth_Token_Str
        header_body_split = endpoint_split[1].split(delim, 1)

        self.header = header_body_split[0]
        self.body = ''
        if len(header_body_split) > 1:
            self.body = header_body_split[1].rstrip('\r\n')

        if ignore_dynamic_objects:
            self._remove_dynamic_objects()

    def __hash__(self):
        return hash((self.method, self.endpoint, self.body))

    def __eq__(self, other):
        if not isinstance(other, ParsedRequest):
            return False

        return self.method == other.method and\
               self.endpoint == other.endpoint and\
               self.body == other.body

    @property
    def authorization_token(self):
        """ Extracts the authorization token from the header
        Returns None if it is not found.
        """
        try:
            header_split = self.header.split('\r\n')
            Auth_Line = 'Authorization: '
            for line in header_split:
                if line.startswith(Auth_Line):
                    return line.split(Auth_Line)[1]
        except:
            return None

    def _remove_dynamic_objects(self):
        """ Helper function that parses a request's endpoint and
        body to replace dynamic objects.

        The purpose of this function is to remove unique identifiers from
        requests in order to diff two runs of the same RESTler job

        The function looks for the unit test resource identifier <test!>
        and then replaces any resources with that identifier with a
        string surrounded by brackets that can be compared across multiple
        different fuzzing runs.

        """
        # split the endpoint at each /
        vals = self.endpoint.split('/')
        for i, val in enumerate(vals):
            # Find each dynamic object that contains the identifier and
            # replace the split values list with the new non-dynamic value
            if UNIT_TEST_RESOURCE_IDENTIFIER in val:
                vals[i] = f'{{{val.split(UNIT_TEST_RESOURCE_IDENTIFIER)[0]}}}'

        self.endpoint = ''
        # Iterate through the updated values list to create the new endpoint
        for val in vals[1:]:
            self.endpoint += f'/{val}'

        if self.body and len(self.body) > 2:
            # Split the body by double-quotes
            vals = self.body.split('"')
            for i, val in enumerate(vals):
                # Find each dynamic object that contains the identifier and
                # replace the split values list with the new non-dynamic value
                if UNIT_TEST_RESOURCE_IDENTIFIER in val:
                    vals[i] = f'{{{val.split(UNIT_TEST_RESOURCE_IDENTIFIER)[0]}}}'

            self.body = '{'
            # Iterate through the updated values list to create the new body
            for val in vals[1:]:
                self.body += f'"{val}'

class ParsedSequence:
    """ A sequence of ParsedRequest objects """
    def __init__(self, requests: list):
        self.requests = requests
        # OrderedDict required for testing the order that checkers are run.
        self.checker_requests = OrderedDict()

    def __eq__(self, other):
        if not isinstance(other, ParsedSequence):
            return False

        return self.requests == other.requests and\
               self.checker_requests == other.checker_requests

    def __iter__(self):
        return iter(self.requests)

    def __add__(self, request: ParsedRequest):
        return ParsedSequence(self.requests + [request])

    def __len__(self):
        return len(self.requests)
