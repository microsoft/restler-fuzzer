# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from engine.fuzzing_parameters.request_params import *
from engine.fuzzing_parameters.request_schema_parser import *
from engine.fuzzing_parameters.body_schema import BodySchema
import utils.logger as logger

class NoExamplesFound(Exception):
    pass

class RequestExamples():
    """ Request Examples Class. """

    def __init__(self, request_schema_json):
        """ Initialize and construct the RequestExamples by deserializing the
        compiler generated request schema IL.

        @param request_schema_json: Compiler generated request schema IL
        @type  request_schema_json: JSON

        @return: None
        @rtype:  None

        """
        # initialization
        self._query_examples: set = set()   # {QueryList}
        self._body_examples: set = set()    # {BodySchema}

        # process the request schema
        try:
            self._set_query_params(request_schema_json['queryParameters'])
        except Exception as err:
            msg = f'Fail deserializing request schema query examples: {err!s}'
            logger.write_to_main(msg, print_to_console=True)
            raise Exception(msg)

        try:
            self._set_body_params(request_schema_json['bodyParameters'])
        except Exception as err:
            msg = f'Fail deserializing request schema body examples: {err!s}'
            logger.write_to_main(msg, print_to_console=True)
            raise Exception(msg)

        if not self._query_examples and not self._body_examples:
            raise NoExamplesFound

    @property
    def body_examples(self):
        """ Return the body examples

        @return: Body examples
        @rtype:  Set {BodySchema}

        """
        return self._body_examples

    @property
    def query_examples(self):
        """ Return the query examples

        @return: Query examples
        @rtype:  Set {ParamObject}

        """
        return self._query_examples

    def _set_query_params(self, query_parameters):
        """ Deserializes and populates the query parameters

        @param query_parameters: Query parameters from request schema
        @param query_parameters: JSON

        @return: None
        @rtype : None

        """
        # Iterate through each collection of query parameters
        for query_parameter in query_parameters:
            if query_parameter[0] == 'Examples':
                query_list = QueryList()
                # Set each query parameter of the query
                for query in des_query_param(query_parameter[1]):
                    query_list.append(query)
                self._query_examples.add(query_list)

    def _set_body_params(self, body_parameters):
        """ Deserializes and populates the body parameters

        @param body_parameters: Body parameters from request schema
        @param body_parameters: JSON

        @return: None
        @rtype : None

        """
        # Iterate through each body parameter
        for body_parameter in body_parameters:
            if body_parameter[0] == 'Examples':
                payload = des_body_param(body_parameter[1])
                if payload:
                    body_example = des_param_payload(payload)
                    if body_example:
                        self._body_examples.add(BodySchema(param=body_example))
