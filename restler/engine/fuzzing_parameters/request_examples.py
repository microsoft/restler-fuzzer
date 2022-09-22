# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from engine.fuzzing_parameters.request_params import *
from engine.fuzzing_parameters.request_schema_parser import *
from engine.fuzzing_parameters.body_schema import BodySchema
from engine.fuzzing_parameters.parameter_schema import QueryList
from engine.fuzzing_parameters.parameter_schema import HeaderList
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
        self._query_examples: list = []   # {QueryList}
        self._header_examples: list = []   # {HeaderList}
        self._body_examples: list = []    # {BodySchema}

        # process the request schema
        try:
            self._set_query_params(request_schema_json['queryParameters'])
        except Exception as err:
            msg = f'Fail deserializing request schema query examples: {err!s}'
            logger.write_to_main(msg, print_to_console=True)
            raise Exception(msg)

        try:
            self._set_header_params(request_schema_json['headerParameters'])
        except Exception as err:
            msg = f'Fail deserializing request schema header examples: {err!s}'
            logger.write_to_main(msg, print_to_console=True)
            raise Exception(msg)

        try:
            self._set_body_params(request_schema_json['bodyParameters'])
        except Exception as err:
            msg = f'Fail deserializing request schema body examples: {err!s}'
            logger.write_to_main(msg, print_to_console=True)
            raise Exception(msg)

        if not (self._query_examples or self._body_examples or self._header_examples):
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

    @property
    def header_examples(self):
        """ Return the header examples

        @return: Header examples
        @rtype:  Set {ParamObject}

        """
        return self._header_examples

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
                self._query_examples.append(query_list)

    def _set_header_params(self, header_parameters):
        """ Deserializes and populates the header parameters

        @param query_parameters: Header parameters from request schema
        @param query_parameters: JSON

        @return: None
        @rtype : None

        """
        # Special case: 'DictionaryCustomPayload' may contain the 'Content-Type' parameter
        content_type_headers = []
        for header_parameter in header_parameters:
            if header_parameter[0] == 'DictionaryCustomPayload':
                # Save this and later append to every example parameter
                for header in des_header_param(header_parameter[1]):
                    content_type_headers.append(header)
                break

        # Iterate through each collection of header parameters
        for header_parameter in header_parameters:
            if header_parameter[0] == 'Examples':
                header_list = HeaderList()
                # Set each header parameter of the query
                for header in des_header_param(header_parameter[1]):
                    header_list.append(header)
                for header in content_type_headers:
                    header_list.append(header)
                self._header_examples.append(header_list)

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
                added_body = False
                if payload:
                    body_example = des_param_payload(payload)
                    if body_example:
                        self._body_examples.append(BodySchema(param=body_example))
                        added_body = True
                if not added_body:
                    # Add a None value in the array to track that this example has no body
                    self._body_examples.append(None)
