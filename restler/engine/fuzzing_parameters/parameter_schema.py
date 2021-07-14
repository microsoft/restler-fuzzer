# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
import json
from abc import ABCMeta, abstractmethod

from engine.fuzzing_parameters.request_params import *
from engine.fuzzing_parameters.request_schema_parser import *
import utils.logger as logger

class NoHeaderSchemaFound(Exception):
    pass

class NoQuerySchemaFound(Exception):
    pass

class KeyValueParamList():
    __metaclass__ = ABCMeta

    """ List of QueryParam or HeaderParam objects
    """
    def __init__(self):
        """ Initializes the QueryList
        """
        self._param_list = []

    @property
    def param_list(self):
        return self._param_list

    def __iter__(self):
        # TODO: test examples checker w/ this change...
        for param_item in self._param_list:
            yield param_item

    def __len__(self):
        return len(self._param_list)

    def __eq__(self, other):
        """ Operator equals
        """
        if not isinstance(other, KeyValueParamList):
            # don't attempt to compare against unrelated types
            return False

        return self._param_list == other.param_list

    def __hash__(self):
        """ Custom hash function
        """
        _hash = 0
        for param_item in self._param_list:
            _hash += hash(param_item)
        return _hash

    def append(self, param_item):
        """ Appends a new query to the end of the Query List

        @param query: The new query to append
        @type  query: QueryParam

        @return: None
        @rtype : None

        """
        self.param_list.append(param_item)

class QueryList(KeyValueParamList):
    def __init__(self, request_schema_json=None, param=None):
        """ Initializes the QueryList
        @param request_schema_json: Compiler generated request schema
        @type  request_schema_json: JSON
        @param param: Query schema as a QueryList
        @type  param: QueryList

        @return: None
        @rtype:  None

        """
        KeyValueParamList.__init__(self)

        if param:
            self._param_list = param

        if request_schema_json:
            try:
                self._set_query_schema(request_schema_json['queryParameters'])
            except NoQuerySchemaFound:
                raise
            except Exception as err:
                msg = f'Fail deserializing request schema query parameters: {err!s}'
                logger.write_to_main(msg, print_to_console=True)
                raise err

    def _set_query_schema(self, query_parameters):
        """ Deserializes and populates the query list

        @param query_parameters: Query parameters from request schema
        @param query_parameters: JSON

        @return: None
        @rtype : None

        """
        for query_parameter in query_parameters:
            if query_parameter[0] == 'Schema':
                # Set each query parameter of the query
                query_param_list = des_query_param(query_parameter[1])
                if query_param_list:
                    for query_param in query_param_list:
                        self.append(query_param)

class HeaderList(KeyValueParamList):
    def __init__(self, request_schema_json=None, param=None):
        """ Initializes the HeaderList
        @param request_schema_json: Compiler generated request schema
        @type  request_schema_json: JSON
        @param param: Header schema as a HeaderList
        @type  param: HeaderList

        @return: None
        @rtype:  None

        """
        KeyValueParamList.__init__(self)

        if param:
            self._param_list = param

        if request_schema_json:
            try:
                if 'headerParameters' in request_schema_json: # check for backwards compatibility of old schemas
                    self._set_header_schema(request_schema_json['headerParameters'])
            except NoHeaderSchemaFound:
                raise
            except Exception as err:
                msg = f'Fail deserializing request schema header parameters: {err!s}'
                logger.write_to_main(msg, print_to_console=True)
                raise err

    def _set_header_schema(self, header_parameters):
        """ Deserializes and populates the header list

        @param header_parameters: Header parameters from request schema
        @param header_parameters: JSON

        @return: None
        @rtype : None

        """
        for header_parameter in header_parameters:
            if header_parameter[0] == 'Schema':
                # Set each query parameter of the query
                header_param_list = des_header_param(header_parameter[1])
                if header_param_list:
                    for header_param in header_param_list:
                        self.append(header_param)

