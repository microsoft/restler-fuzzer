# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
import json
from abc import ABCMeta, abstractmethod

from engine.fuzzing_parameters.request_params import *
from engine.fuzzing_parameters.request_schema_parser import *
import engine.primitives as primitives
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

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamObject]

        """
        fuzzed_members = []
        for param_item in self.param_list:
            item_fuzzing_pool = param_item.get_fuzzing_pool(fuzzer, config)  #list of key=value pairs
            # It is possible that this member was excluded from fuzzing by
            # a filter configured by the fuzzer.  If so, do not add it to
            # 'fuzzed_members'.
            if len(item_fuzzing_pool) > 0:
                fuzzed_members.append(item_fuzzing_pool)

        return fuzzer._fuzz_param_list(fuzzed_members)  # list of lists of key=value pairs

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
            if query_parameter[0] in ['Schema', 'DictionaryCustomPayload']:
                # Set each query parameter of the query
                query_param_list = des_query_param(query_parameter[1])
                if query_param_list:
                    for query_param in query_param_list:
                        self.append(query_param)

    def get_blocks(self) -> list:
        """ Returns the request blocks for the query list

        @return: The request blocks for this schema
        @rtype : List[]

        """
        query_blocks = []
        for idx, query in enumerate(self.param_list):
            query_blocks += query.get_blocks()
            if idx < len(self.param_list) - 1:
                # Add the query separator
                query_blocks.append(primitives.restler_static_string('&'))
        return query_blocks

    def get_original_blocks(self, config) -> list:
        """ Returns the request blocks for the query list
            as they were declared in the original schema.

        @return: The request blocks for this schema
        @rtype : List[]

        """
        query_blocks = []
        for idx, query in enumerate(self.param_list):
            query_blocks += query.get_original_blocks(config)
            if len(query_blocks) > 0 and idx < len(self.param_list) - 1:
                # Add the query separator
                query_blocks.append(primitives.restler_static_string('&'))
        return query_blocks


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
            if header_parameter[0] in ['Schema', 'DictionaryCustomPayload']:
                # Set each query parameter of the query
                header_param_list = des_header_param(header_parameter[1])
                if header_param_list:
                    for header_param in header_param_list:
                        self.append(header_param)

    def get_blocks(self) -> list:
        """ Returns the request blocks for the header list

        @return: The request blocks for this schema
        @rtype : List[]

        """
        header_blocks = []
        for idx, header in enumerate(self.param_list):
            header_blocks += header.get_blocks()
            if len(header_blocks) > 0 and idx < len(self.param_list):
                # Must add header separator \r\n after every header
                header_blocks.append(primitives.restler_static_string('\r\n'))
        return header_blocks

    def get_original_blocks(self, config) -> list:
        """ Returns the request blocks as they were originally declared
        in the schema.

        @return: The request blocks for this schema
        @rtype : List[]

        """
        header_blocks = []
        for idx, header in enumerate(self.param_list):
            header_blocks += header.get_original_blocks(config)
            if len(header_blocks) > 0 and idx < len(self.param_list):
                # Must add header separator \r\n after every header
                header_blocks.append(primitives.restler_static_string('\r\n'))
        return header_blocks