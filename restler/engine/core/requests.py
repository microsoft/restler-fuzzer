# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Primitives for definition and manipulation of restler request sequences. """
from __future__ import print_function
import time
import types
import random
random.seed(12345)
import itertools
import collections
import datetime
import copy

from restler_settings import Settings
import engine.core.request_utilities as request_utilities
from engine.core.request_utilities import str_to_hex_def
from engine.fuzzing_parameters.request_examples import RequestExamples
from engine.fuzzing_parameters.body_schema import BodySchema
from engine.fuzzing_parameters.parameter_schema import QueryList
from engine.fuzzing_parameters.parameter_schema import HeaderList
import engine.fuzzing_parameters.param_combinations as param_combinations

from engine.errors import InvalidDictionaryException
import utils.logger as logger
import engine.primitives as primitives
import engine.dependencies as dependencies
import engine.mime.multipart_formdata as multipart_formdata
from enum import Enum
from engine.transport_layer import messaging

class EmptyRequestException(Exception):
    pass

class InvalidGrammarException(Exception):
    pass

class FailureInformation(Enum):
    SEQUENCE = 1
    RESOURCE_CREATION = 2
    PARSER = 3
    BUG = 4
    MISSING_STATUS_CODE = 5

class RenderedRequestStats(object):
    """ Class used for encapsulating data about a specific rendered request and its response.
        This data is included in the spec coverage report.
        However, this data includes run-specific information
        and should not be used for diffing spec coverage. """
    def __init__(self):
        self.request_sent_timestamp = None
        self.response_received_timestamp = None

        self.request_verb = None
        self.request_uri = None
        self.request_headers = None
        self.request_body = None

        self.response_status_code = None
        self.response_status_text = None
        self.response_headers = None
        self.response_body = None

    def set_request_stats(self, request_text):
        """ Helper to set the request statistics from the text.
            Parses the request text and initializes headers, uri, and body
            separately.

        @return: None
        @rtype : None

        """
        try:
            split_body = request_text.split(messaging.DELIM)
            split_headers = split_body[0].split("\r\n")
            verb_and_uri = split_headers[0].split(" ")
            self.request_verb = verb_and_uri[0]
            self.request_uri = verb_and_uri[1]
            self.request_headers = split_headers[1:]

            # Remove the value of the Authorization header,
            # so it is not persisted in logs
            for idx, h in enumerate(self.request_headers):
                if h.startswith("Authorization:"):
                    self.request_headers[idx] = "Authorization: _OMITTED_AUTH_TOKEN_"

            if len(split_body) > 0 and split_body[1]:
                self.request_body = split_body[1]
        except:
            logger.write_to_main(
                            f"Error setting request stats for text: {request_text}",
                            print_to_console=True
                        )
            pass

    def set_response_stats(self, final_request_response, final_response_datetime):
        """ Helper to set the response headers and body.

        @return: None
        @rtype : None

        """
        self.response_status_code = final_request_response.status_code
        self.response_status_text = final_request_response.status_text
        self.response_headers = final_request_response.headers
        self.response_body = final_request_response.body
        self.response_received_timestamp = final_response_datetime


class SmokeTestStats(object):
    """ Class used for logging stats during directed-smoke-test """
    def __init__(self):
        self.request_order = -1
        self.matching_prefix = {} # {"id": <prefix_hex>, "valid": <0/1>}
        self.valid = 0
        self.has_valid_rendering = 0
        self.failure = None

        self.error_msg = None
        self.status_code = None
        self.status_text = None

        self.sample_request = None
        self.sequence_failure_sample_request = None
        self.tracked_parameters = {}

    def set_matching_prefix(self, sequence_prefix):
        # Set the prefix of the request, if it exists.
        if len(sequence_prefix.requests) > 0:
            prefix_ids = []
            for c in sequence_prefix.current_combination_id:
                prefix_id = {}
                prefix_id["id"] = c
                if self.valid:
                    prefix_id["valid"] = self.valid
                prefix_ids.append(prefix_id)
            self.matching_prefix = prefix_ids

    def set_all_stats(self, renderings):

        self.valid = 1 if renderings.valid else 0
        if self.valid:
            self.has_valid_rendering = 1
        self.failure = renderings.failure_info

        # Get the last rendered request.  The corresponding response should be
        # the last received response.
        if renderings.sequence:
            self.set_matching_prefix(renderings.sequence.prefix)
            if self.failure == FailureInformation.SEQUENCE:
                self.sequence_failure_sample_request = RenderedRequestStats()
                self.sequence_failure_sample_request.set_request_stats(
                    renderings.sequence.sent_request_data_list[-1].rendered_data)
                self.sequence_failure_sample_request.set_response_stats(renderings.final_request_response,
                                                                        renderings.final_response_datetime)
            else:
                self.status_code = renderings.final_request_response.status_code
                self.status_text = renderings.final_request_response.status_text

                self.sample_request = RenderedRequestStats()
                self.sample_request.set_request_stats(
                    renderings.sequence.sent_request_data_list[-1].rendered_data)
                self.sample_request.set_response_stats(renderings.final_request_response,
                                                       renderings.final_response_datetime)
                response_body = renderings.final_request_response.body

                if not renderings.valid:
                    self.error_msg = response_body

            # Set tracked parameters
            last_req = renderings.sequence.last_request

            # extract the custom payloads and enums
            for property_name, property_value in last_req._tracked_parameters.items():
                self.tracked_parameters[property_name] = property_value


class Request(object):
    """ Request Class. """
    def __init__(self, definition=[], requestId=None):
        """ Initialize a request object by assigning a definition and
        internally constructing the necessary constraints.

        @param definition: List of restler primitives and directives
                            corresponding to what we call "restler grammar".
        @type  definition: List
        @param requestId: The request's ID string
        @type  requestId: Str

        @return: None
        @rtype : None

        """
        self._current_combination_id = 0
        self._total_feasible_combinations = 0
        self._hex_definition = 0
        self._method_endpoint_hex_definition = 0
        self._request_id = 0
        self._endpoint_no_dynamic_objects = requestId
        self._definition = definition
        self._examples = None
        self._body_schema = None
        self._query_schema = None
        self._headers_schema = None
        self._consumes = set()
        self._produces = set()
        self._set_constraints()
        self._create_once_requests = []
        self._tracked_parameters = {}

        # Check for empty request before assigning ids
        if self._definition:
            self._set_hex_definitions(requestId)
        else:
            raise EmptyRequestException

        if Settings().in_smoke_test_mode():
            self.stats = SmokeTestStats()

    def __iter__(self):
        """ Iterate over Request objects. """
        yield self

    def _set_hex_definitions(self, requestId):
        """ Helper that sets the various hex definition values

        @return: None
        @rtype : None

        """
        self._hex_definition = str_to_hex_def(str(self.definition))

        request_id_component = requestId if requestId else self.endpoint
        self._request_id = str_to_hex_def(request_id_component)
        self._method_endpoint_hex_definition = str_to_hex_def(self.method + request_id_component)

    def _get_var_name_from_definition_line(self, line):
        """ Helper that parses a specified line from the definition
        and returns the variable name, if present.

        @param line: The line to parse
        @type  line: Str

        @return: The variable name, or None
        @rtype : Str

        """
        if isinstance(line[1], str)\
        and line[1].startswith(dependencies.RDELIM):
            return line[1].split(dependencies.RDELIM)[1]
        return None

    def _set_constraints(self):
        """ Helper that produces constraints based on the producer/consumer
        relationships defined in the body of requests.

        @return: None
        @rtype : None

        """
        # Look for reader placeholders
        for line in self.definition:
            var_name = self._get_var_name_from_definition_line(line)
            if var_name:
                self._consumes.add(var_name)
        # Also look for reader placeholders in the pre_send section
        if bool(self.metadata) and 'pre_send' in self.metadata\
        and 'dependencies' in self.metadata['pre_send']:
            for reader_var in self.metadata['pre_send']['dependencies']:
                var_name = reader_var.split(dependencies.RDELIM)[1]
                self._consumes.add(var_name)

        # Look for writer placeholders
        if bool(self.metadata) and 'post_send' in self.metadata\
        and 'dependencies' in self.metadata['post_send']:
            for var_name in self.metadata['post_send']['dependencies']:
                self._produces.add(var_name)

    @property
    def definition(self):
        """ Iterable list representation of request definition.

        @return: Request definition in list representation.
        @rtype : List

        """
        if not self._definition:
            return []

        metadata = self._definition[-1]
        # Skip the last item of the definition list, if it is a dictionary
        # (which containts 'post_send' directives for response parsing
        if isinstance(metadata, dict):
            return self._definition[:-1]

        return self._definition

    @property
    def hex_definition(self):
        """ The hex definition of this request

        @return: The hex definition
        @rtype : Int

        """
        return self._hex_definition

    @property
    def method_endpoint_hex_definition(self):
        """ The hex definition of this request created only from the method and endpoint

        @return: The method-endpoint hex definition
        @rtype : Int

        """
        return self._method_endpoint_hex_definition

    @property
    def request_id(self):
        """ ID of this Request object

        Note: This is defined from the endpoint string specified in
        the grammar. It is not necessarily a unique ID, as it does
        not include the request's method.

        @return: The Request ID
        @rtype : Int
        """
        return self._request_id

    @property
    def endpoint_no_dynamic_objects(self):
        """ Endpoint of this Request as seen in the swagger

        @return: The endpoint
        @rtype : Str

        """
        return self._endpoint_no_dynamic_objects

    @property
    def metadata(self):
        """ Returns the "post_send" dictionary of a request definition which is
        basically metadata defining producer dependencies & respective response
        parser.

        @return: Metadata of empty dictionary if no interesting metadata exist.
        @rtype : Dict

        """
        if not self._definition:
            return {}

        metadata = self._definition[-1]
        if isinstance(metadata, dict):
            return metadata

        return {}

    @property
    def method(self):
        """ Returns the request's HTTP method

        @return: The request's HTTP method
        @rtype : Str

        """
        return self._definition[0][1].rstrip()


    @property
    def endpoint(self):
        """ Returns the request's endpoint

        @return: The request's endpoint
        @rtype : Str

        """
        endpoint_string = ""
        for request_block in self._definition[1:]:
            payload = str(request_block[1])
            if "?" in payload or "HTTP" in payload:
                break
            endpoint_string += payload

        return endpoint_string

    @property
    def examples(self) -> RequestExamples:
        """ Returns the Request's examples

        @return: The Request's examples

        """
        return self._examples

    @property
    def body_schema(self) -> BodySchema:
        """ Returns the Request's body schema

        @return: The Request's body schema

        """
        return self._body_schema

    @property
    def query_schema(self) -> QueryList:
        """ Returns the Request's query schema

        @return: The Request's query schema

        """
        return self._query_schema

    @property
    def headers_schema(self) -> HeaderList:
        """ Returns the Request headers schema

        @return: The Request headers schema
        """
        return self._headers_schema

    @property
    def consumes(self) -> set:
        """ Returns the set of dynamic objects that this request consumes

        @return: The dynamic objects that this request consumes

        """
        return set(self._consumes)

    @property
    def produces(self) -> set:
        """ Returns the set of dynamic objects that this request produces

        @return: The dynamic objects that this request produces

        """
        return set(self._produces)

    @property
    def create_once_requests(self) -> list:
        """ Returns the list of create once request renderings used to
        create this request

        @return: list[Str]

        """
        return list(self._create_once_requests) if self._create_once_requests else None

    def is_consumer(self) -> bool:
        """ Returns whether or not this request is a consumer

        @return: True if this request consumes any dynamic objects
        @rtype : Bool

        """
        return bool(self._consumes)

    def set_examples(self, examples: RequestExamples):
        """ Sets the Request's examples

        @param examples: The examples to set

        @return: None

        """
        self._examples = examples

    def set_body_schema(self, body_schema: BodySchema):
        """ Sets the Request's body schema

        @param body_schema: The body schema to set

        @return: None

        """
        self._body_schema = body_schema

    def set_query_schema(self, query_schema: QueryList):
        """ Sets the Request's query schema

        @param query_schema: The query schema to set

        @return: None

        """
        self._query_schema = query_schema

    def set_headers_schema(self, headers_schema: HeaderList):
        """ Sets the Request headers schema

        @param headers_schema: The headers schema to set

        @return: None

        """
        self._headers_schema = headers_schema

    def is_destructor(self):
        """ Checks whether the current request object instance is a destructor.

        @return: True, if the current request is a destructor, i.e., a DELETE
        method.
        @rtype : Bool

        """
        if 'DELETE' in self.method:
            return True
        return False

    def is_resource_generator(self):
        """ Checks whether the current request object instance is a producer that
            is likely to create a new resource.

        @return: True, if the current request is a producer and executes a POST method.
        method.
        @rtype : Bool

        """
        if 'POST' in self.method or 'PUT' in self.method:
            if bool(self.metadata) and 'post_send' in self.metadata\
            and 'parser' in self.metadata['post_send']:
                return True
        return False

    def set_id_values_for_create_once_dynamic_objects(self, dynamic_object_values, rendered_sequence):
        """ Sets the ID values for specified dynamic object values in the request definition.
        The function iterates through the definition and replaces the variable
        names specified in the @param dynamic_object_values dictionary with
        the values associated with them. That variable is then removed as a consumer
        for this request because that variable will now be replaced with what can
        be thought of as a static_string (not dynamic).

        @param dynamic_object_values: Dictionary of dynamic object names and values
        @type  dynamic_object_values: Dict
        @param rendered_sequence: The rendered create-once sequence that was sent to create the dynamic objects
        @type  rendered_sequence: RenderedSequence

        @return: None
        @rtype : None

        """
        for i, line in enumerate(self.definition):
            var_name = self._get_var_name_from_definition_line(line)
            if var_name and var_name in dynamic_object_values:
                self._definition[i] =\
                    primitives.restler_static_string(dynamic_object_values[var_name])
                # Remove the variable from consumers, because the reader has
                # been removed from the definition.
                if var_name in self._consumes:
                    self._consumes.remove(var_name)
        self._create_once_requests += rendered_sequence.sequence.sent_request_data_list

    def get_host_index(self):
        """ Gets the index of the definition line containing the Host parameter

        @return: The index of the Host parameter or -1 if not found
        @rtype : Int

        """
        for i, line in enumerate(self._definition):
            try:
                if isinstance(line[1], str) and line[1].startswith(request_utilities.HOST_PREFIX):
                    return i
            except:
                # ignore line parsing exceptions - error will be returned if host not found
                pass
        return -1

    def get_basepath_index(self):
        """ Gets the index of the basepath custom payload line, if it exists in the grammar.

        @return: The index of the basepath parameter or -1 if not found
        @rtype : Int

        """
        for i, line in enumerate(self._definition):
            try:
                if line[0] == "restler_basepath":
                    return i
            except:
                # ignore line parsing exceptions
                pass
        return -1

    def update_host(self):
        """ Updates the Host field for every request with the one specified in Settings

        @return: None
        @rtype : None

        """
        new_host_line = primitives.restler_static_string(f"{request_utilities.HOST_PREFIX}{Settings().host}\r\n")
        host_idx = self.get_host_index()
        if host_idx >= 0:
            self._definition[host_idx] = new_host_line
        else:
            # Host not in grammar, add it
            header_idx = self.header_start_index()
            if header_idx < 0:
                raise InvalidGrammarException
            self._definition.insert(header_idx, new_host_line)

    def update_basepath(self):
        """ Updates the basepath custom payload for every request with the one specified in Settings

        @return: None
        @rtype : None

        """
        basepath_idx = self.get_basepath_index()
        if basepath_idx >= 0:
            basepath = self._definition[basepath_idx][1]
            if Settings().basepath is not None:
                basepath = Settings().basepath
            self._definition[basepath_idx] = primitives.restler_static_string(basepath)
        else:
            # No basepath custom payload in the grammar - this is possible for older grammar versions.
            # Do nothing
            pass

    def header_start_index(self):
        """ Gets the index of the first header line in the definition

        @return: The index of the first header line in the definition or -1 if not found
        @rtype : Int

        """
        for i, line in enumerate(self._definition):
            if isinstance(line[1], str) and 'HTTP/1.1' in line[1]:
                return i + 1
        return -1

    def get_schema_combinations(self):
        """ A generator that lazily iterates over a pool of schema combinations
        for this request, determined the specified settings.

        By default, only one schema combination is tested, which is the default
        specified in the grammar.

        Optionally, various parameter combinations and example payload schemas
        may be tested.

        Currently, combinations for each parameter type are tested independently.
        For example, if there are 4 query parameter combinations and 4 header
        parameter combinations, there will be a total of 8 combinations.

        @return: (One or more copies of the request, each with a unique schema)
        @rtype : (Request)

        """
        tested_example_payloads = False
        example_payloads = Settings().example_payloads
        if example_payloads is not None and self.examples is not None:
            tested_example_payloads = True
            for ex in self.get_example_payloads(example_payloads):
                yield ex

        tested_param_combinations = False
        header_param_combinations = Settings().header_param_combinations
        if header_param_combinations is not None:
            tested_param_combinations = True
            for hpc in self.get_header_param_combinations(header_param_combinations):
                yield hpc

        query_param_combinations = Settings().query_param_combinations
        if query_param_combinations is not None:
            tested_param_combinations = True
            for hpc in self.get_query_param_combinations(query_param_combinations):
                yield hpc

        if not (tested_param_combinations or tested_example_payloads):
            yield self

    def init_fuzzable_values(self, req_definition, candidate_values_pool, preprocessing=False):

        fuzzable = []
        writer_variables=[]
        # The following list will contain name-value pairs of properties whose combinations
        # are tracked for coverage reporting purposes.
        # First, in the loop below, the index of the property in the values list will be added.
        # Then, at the time of returning the specific combination of values, a new list with
        # the values will be created
        tracked_parameters = {}

        for request_block in req_definition:
            primitive_type = request_block[0]
            writer_variable = None

            if primitive_type == primitives.FUZZABLE_GROUP:
                field_name = request_block[1]
                default_val = request_block[2]
                quoted = request_block[3]
                examples = request_block[4]
                writer_variable = request_block[6]
            elif primitive_type in [ primitives.CUSTOM_PAYLOAD,
                                     primitives.CUSTOM_PAYLOAD_HEADER,
                                     primitives.CUSTOM_PAYLOAD_QUERY,
                                     primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX ]:
                field_name = request_block[1]
                quoted = request_block[2]
                examples = request_block[3]
                writer_variable = request_block[5]
            else:
                default_val = request_block[1]
                quoted = request_block[2]
                examples = request_block[3]
                field_name = request_block[4]
                writer_variable = request_block[5]

            values = []
            # Handling dynamic primitives that need fresh rendering every time
            if primitive_type == primitives.FUZZABLE_UUID4:
                if quoted:
                    values = [(primitives.restler_fuzzable_uuid4, True, writer_variable)]
                else:
                    values = [(primitives.restler_fuzzable_uuid4, False, writer_variable)]
            # Handle enums that have a list of values instead of one default val
            elif primitive_type == primitives.FUZZABLE_GROUP:
                if quoted:
                    values = [f'"{val}"' for val in default_val]
                else:
                    values = list(default_val)
            # Handle static whose value is the field name
            elif primitive_type == primitives.STATIC_STRING:
                val = default_val
                if val == None:
                    # the examplesChecker may inject None/null, so replace these with the string 'null'
                    logger.raw_network_logging(f"Warning: there is a None value in a STATIC_STRING.")
                    val = 'null'
                    # Do not quote null values.
                    quoted = False
                if quoted:
                    val = f'"{val}"'
                values = [val]
            # Handle multipart form data
            elif primitive_type == primitives.FUZZABLE_MULTIPART_FORMDATA:
                try:
                    current_fuzzable_values = candidate_values_pool.\
                        get_candidate_values(primitive_type, request_id=self._request_id, tag=default_val, quoted=quoted)
                    values = [multipart_formdata.render(current_fuzzable_values)]
                except primitives.CandidateValueException:
                    _raise_dict_err(primitive_type, default_val)
                except Exception as err:
                    _handle_exception(primitive_type, default_val, err)
            # Handle custom (user defined) static payload
            elif primitive_type == primitives.CUSTOM_PAYLOAD:
                try:
                    current_fuzzable_values = candidate_values_pool.\
                        get_candidate_values(primitive_type, request_id=self._request_id, tag=field_name, quoted=quoted)
                    # handle case where custom payload have more than one values
                    if isinstance(current_fuzzable_values, list):
                        values = current_fuzzable_values
                    else:
                        values = [current_fuzzable_values]
                except primitives.CandidateValueException:
                    _raise_dict_err(primitive_type, field_name)
                except Exception as err:
                    _handle_exception(primitive_type, field_name, err)

            # Handle custom (user defined) static payload on header or query
            elif (primitive_type == primitives.CUSTOM_PAYLOAD_HEADER or\
                  primitive_type == primitives.CUSTOM_PAYLOAD_QUERY):
                try:
                    current_fuzzable_values = candidate_values_pool.\
                        get_candidate_values(primitive_type, request_id=self._request_id, tag=field_name, quoted=quoted)
                    # handle case where custom payload have more than one values
                    if isinstance(current_fuzzable_values, list):
                        values = current_fuzzable_values
                    else:
                        values = [current_fuzzable_values]
                except primitives.CandidateValueException:
                    _raise_dict_err(primitive_type, field_name)
                except Exception as err:
                    _handle_exception(primitive_type, field_name, err)

            # Handle custom (user defined) static payload with uuid4 suffix
            elif primitive_type == primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX:
                try:
                    current_fuzzable_value = candidate_values_pool.\
                        get_candidate_values(primitive_type, request_id=self._request_id, tag=field_name, quoted=quoted)

                    # Replace the custom payload type with the specified value, but keep all others the same
                    # Assert if the request block does not match the expected definition
                    if len(request_block) != 6:
                        raise Exception("Request block definition is expected to have 6 elements.")
                    current_uuid4_suffix = primitives.restler_custom_payload_uuid4_suffix(
                                                current_fuzzable_value,
                                                quoted=request_block[2],
                                                examples=request_block[3],
                                                param_name=request_block[4],
                                                writer=request_block[5])
                    values = [current_uuid4_suffix]
                except primitives.CandidateValueException:
                    _raise_dict_err(primitive_type, field_name)
                except Exception as err:
                    _handle_exception(primitive_type, field_name, err)
            elif primitive_type == primitives.REFRESHABLE_AUTHENTICATION_TOKEN:
                values = [primitives.restler_refreshable_authentication_token]
            # Handle all the rest
            else:
                values = candidate_values_pool.get_fuzzable_values(primitive_type, default_val, self._request_id, quoted, examples)

            if Settings().fuzzing_mode == 'random-walk' and not preprocessing:
                random.shuffle(values)

            if len(values) == 0:
                _raise_dict_err(primitive_type, current_fuzzable_tag)

            # When testing all combinations, update tracked parameters.
            if Settings().fuzzing_mode == 'test-all-combinations':
                param_idx = len(fuzzable)
                # Only track the parameter if there are multiple values being combined
                if len(values) > 1:
                    if not field_name:
                        field_name = f"tracked_param_{param_idx}"
                    if field_name not in tracked_parameters:
                        tracked_parameters[field_name] = []
                    tracked_parameters[field_name].append(param_idx)

            fuzzable.append(values)
            writer_variables.append(writer_variable)

        return fuzzable, writer_variables, tracked_parameters

    def render_iter(self, candidate_values_pool, skip=0, preprocessing=False):
        """ This is the core method that renders values combinations in a
        request template. It basically is a generator which lazily iterates over
        a pool of possible combination of values that fit the template of the
        requst. Static primitive types (such as, string or delimiters) are
        picked from @param candidate_values_pool; dynamic primitive types
        (such as, uuid4) are generated "fresh" every time the generator yields
        with the help of @method resolve_dynamic_primitives.

        @param candidate_values_pool: The pool of values for primitive types.
        @type candidate_values_pool: Dict
        @param skip: Number of combinations to skip (i.e., not render). This is
                        useful when we use a request as an "ingredient" of a
                        sequence and we are only interested in using a specific
                        rendering that, we know, leads to a valid rendering with
                        a desired status code response.
        @type skip: Int
        @param preprocessing: Set to True if this rendering is happening during preprocessing
        @type  preprocessing: Bool

        @return: (rendered request's payload, response's parser function)
        @rtype : (Str, Function Pointer, List[Str])

        """
        def _raise_dict_err(type, tag):
            logger.write_to_main(
                f"Error for request {self.method} {self.endpoint_no_dynamic_objects}.\n"
                f"{type} exception: {tag} not found.\n"
                "Make sure you are using the dictionary created during compilation.",
                print_to_console=True
            )
            raise InvalidDictionaryException

        def _handle_exception(type, tag, err):
            logger.write_to_main(
                f"Exception when rendering request {self.method} {self.endpoint_no_dynamic_objects}.\n"
                f"Type: {type}. Tag: {tag}.\n"
                f"  Exception: {err!s}",
                print_to_console=True
            )
            raise InvalidDictionaryException

        if not candidate_values_pool:
            print("Candidate values pool empty")
            print(self._definition)
            yield []
            return

        definition = self.definition
        if not definition:
            yield []
            return

        # If multiple schemas are being tested, generate the schemas.  Note: these should be lazily
        # constructed, since not all of them may be needed, e.g. during smoke test mode.
        next_combination = 0
        for req in self.get_schema_combinations():
            parser = None
            # If request had post_send metadata, register parsers etc.
            if bool(self.metadata) and 'post_send' in self.metadata\
            and 'parser' in self.metadata['post_send']:
                parser = self.metadata['post_send']['parser']

            fuzzable, writer_variables, tracked_parameters = self.init_fuzzable_values(req.definition, candidate_values_pool, preprocessing)

            # lazy generation of pool for candidate values
            combinations_pool = itertools.product(*fuzzable)
            combinations_pool = itertools.islice(combinations_pool,
                                                 Settings().max_combinations)

            # skip combinations, if asked to
            while next_combination < skip:
                try:
                    next(combinations_pool)
                    next_combination = next_combination + 1
                except StopIteration:
                    break
                if next_combination == skip:
                    break
            if next_combination < skip:
                continue  # go to the next schema to find combination

            # for each combination's values render dynamic primitives and resolve
            # dependent variables
            for ind, values in enumerate(combinations_pool):
                values = list(values)
                values = request_utilities.resolve_dynamic_primitives(values, candidate_values_pool)
                for val_idx, val in enumerate(values):
                    if writer_variables[val_idx] is not None:
                        dependencies.set_variable(writer_variables[val_idx], val)

                tracked_parameter_values = {}
                for (k, idx_list) in tracked_parameters.items():
                    tracked_parameter_values[k] = []
                    for idx in idx_list:
                        tracked_parameter_values[k].append(values[idx])

                rendered_data = "".join(values)
                yield rendered_data, parser, tracked_parameter_values

    def render_current(self, candidate_values_pool, preprocessing=False):
        """ Renders the next combination for the current request.

        @param candidate_values_pool: The pool of values for primitive types.
        @type candidate_values_pool: Dict
        @param preprocessing: Set to True if this rendering is happening during preprocessing
        @type  preprocessing: Bool

        @return: (rendered request's payload, response's parser function)
        @rtype : (Str, Function Pointer, List[Str])

        """
        return next(self.render_iter(candidate_values_pool,
                                skip=self._current_combination_id - 1,
                                preprocessing=preprocessing))

    def num_combinations(self, candidate_values_pool):
        """ Returns the number of value combination for request's primitive
        types.

        @param candidate_values_pool: The pool of values for primitive types.
        @type candidate_values_pool: Dict

        @return: Number of value combinations.
        @rtype : Int

        """
        # Memoize the last value returned by this function (if invoked)
        if self._total_feasible_combinations:
            return self._total_feasible_combinations

        # Otherwise, do calculation
        counter = 0
        for combination in self.render_iter(candidate_values_pool):
            counter += 1
        self._total_feasible_combinations = counter

        return self._total_feasible_combinations

    def update_tracked_parameters(self, tracked_parameters):
        """ Updates tracked parameters for the request by merging with the
        existing parameters.

        The tracked parameters are currently a set of names, with arrays of
        values that were observed during sequence rendering.

        @param tracked_parameters: The tracked parameters and their values.
        @type tracked_parameters: Dict

        @return: None
        @rtype : None
        """
        for param_name, param_val_list in tracked_parameters.items():
            for param_val in param_val_list:
                if param_name not in self._tracked_parameters:
                    self._tracked_parameters[param_name] = []
                self._tracked_parameters[param_name].append(param_val)

    def get_header_start_end(self):
        """ Get the start and end index of a request's headers

        @param request: The target request
        @type  request: Request

        @return: A tuple containing the start and end index of the header
                [start, end)
        @rtype : Tuple(int, int) or (-1, -1) on failure

        """
        request = self

        header_start_index = self.header_start_index()
        if header_start_index == -1:
            return -1, -1

        # After the headers, there is either a body or they are at the end of the request
        header_end_index = self.get_body_start()
        if header_end_index == -1:
            header_end_index = len(request.definition) #- 1  # The last \r\n should be saved

        return header_start_index, header_end_index

    def substitute_headers(self, new_header_blocks):
        """
        Substitutes the header portion in the old request with the new queries

        @param old_request: The original request
        @type  old_request: Request
        @param new_query_blocks: Request blocks of the new query
        @type  new_query_blocks: List[str]

        @return: The new request
        @rtype : Request or None on failure

        """
        old_request = self
        header_start_index, header_end_index = old_request.get_header_start_end()

        if header_end_index < 0:
            logger.write_to_main("could not get start and end of header")
            return None

        # Get the required header blocks that should always be present
        # These special headers are not fuzzed, and should not be replaced
        skipped_headers_str = ["Accept", "Host", "Content-Type"]
        required_header_blocks = []
        append_header = False
        for line in old_request.definition[header_start_index : header_end_index]:
            if line[0] == "restler_refreshable_authentication_token":
                required_header_blocks.append(line)
                continue
            if append_header:
                required_header_blocks.append(line)
                if line[1].endswith("\r\n"):
                    append_header = False
            for str in skipped_headers_str:
                if line[1].startswith(str):
                    required_header_blocks.append(line)
                    if not line[1].endswith("\r\n"):
                        # Continue to append
                        append_header = True

        # Make sure there is still a delimiter between headers and the remainder of the payload
        new_header_blocks.append(primitives.restler_static_string("\r\n"))
        new_definition = old_request.definition[:header_start_index] + required_header_blocks + new_header_blocks + old_request.definition[header_end_index:]
        new_definition += [old_request.metadata.copy()]
        new_request = Request(new_definition)
        # Update the new Request object with the create once requests data of the old Request,
        # so bug replay logs will include the necessary create once request data.
        new_request._create_once_requests = old_request._create_once_requests
        return new_request

    def get_query_param_combinations(self, query_param_combinations_setting):
        """
        """
        for param_list in param_combinations.get_param_combinations(self, query_param_combinations_setting,
                                                                    self.query_schema.param_list, "query"):
            query_schema = QueryList(param=param_list)
            query_blocks = query_schema.get_blocks()

            new_request = self.substitute_query(query_blocks)
            if new_request:
                yield new_request
            else:
                # For malformed requests, it is possible that the place to insert parameters is not found,
                # In such cases, skip the combination.
                logger.write_to_main(f"Warning: could not substitute query parameters.")

    def get_header_param_combinations(self, header_param_combinations_setting):
        """

        """
        for param_list in param_combinations.get_param_combinations(self, header_param_combinations_setting,
                                                                    self.headers_schema.param_list, "header"):
            headers_schema = HeaderList(param=param_list)
            header_blocks = headers_schema.get_blocks()

            new_request = self.substitute_headers(header_blocks)
            if new_request:
                yield new_request
            else:
                # For malformed requests, it is possible that the place to insert parameters is not found,
                # In such cases, skip the combination.
                logger.write_to_main(f"Warning: could not substitute header parameters.")

    def get_example_payloads(self, example_payloads_setting):
        """
        Replaces the body and query of this request by the available examples.
        Does not currently modify the headers, because header examples are not yet supported.
        """
        # The length of all the example lists is currently expected to be the same.
        num_payloads = len(self.examples.query_examples)
        for payload_idx in range(num_payloads):
            logger.write_to_main(f"Found example {payload_idx}.")
            if len(self.examples.body_examples) <= payload_idx:
                error_message=f"ERROR: ill-formed example {self.endpoint} {self.method}."
                logger.write_to_main(error_message)
                raise Exception(error_message)
            body_example = self.examples.body_examples[payload_idx]
            query_example = self.examples.query_examples[payload_idx]
            # TODO: header examples are not supported yet.
            #  header_example = examples.header_examples[payload_idx]

            # Copy the request definition and reset it here.
            body_blocks = None
            if body_example:
                body_blocks = body_example.get_blocks()
            query_blocks = query_example.get_blocks()

            new_request = self.substitute_query(query_blocks)
            # Only substitute the body if there is a body.
            if body_blocks:
                new_request = new_request.substitute_body(body_blocks)

            if new_request:
                yield new_request
            else:
                # For malformed requests, it is possible that the place to insert query parameters is not found,
                # so the query parameters cannot be inserted. In such cases, skip the example.
                logger.write_to_main(f"Warning: could not substitute example parameters for example {payload_idx}.")

    def get_body_start(self):
        """ Get the starting index of the request body

        @param request: The target request
        @type  request: Request

        @return: The starting index; -1 if not found
        @rtype:  Int or -1 on failure

        """
        request = self
        # search for the first of these patterns in the request definition
        body_start_pattern_dict = primitives.restler_static_string('{')
        body_start_pattern_array = primitives.restler_static_string('[')

        dict_index = -1
        array_index = -1

        try:
            dict_index = request.definition.index(body_start_pattern_dict)
        except Exception:
            pass

        try:
            array_index = request.definition.index(body_start_pattern_array)
        except Exception:
            pass

        if dict_index == -1 or array_index == -1:
            # If one of the indices is -1 then it wasn't found, return the other
            return max(dict_index, array_index)
        # Return the lowest index / first character found in body.
        return min(dict_index, array_index)


    def get_query_start_end(self):
        """ Get the start and end index of a request's query

        @param request: The target request
        @type  request: Request

        @return: A tuple containing the start and end index of the query
        @rtype : Tuple(int, int) or (-1, -1) on failure

        """
        request = self
        query_start_pattern = primitives.restler_static_string('?')
        query_end_str = ' HTTP'
        try:
            query_start_index = request.definition.index(query_start_pattern)
        except:
            # Handle the case where the request does not contain a query
            query_start_index = -1

        query_param_start_index = query_start_index + 1

        for idx, line in enumerate(request.definition[query_param_start_index+1:]):
            if line[1].startswith(query_end_str):
                query_end_index = query_param_start_index + idx + 1
                if query_start_index == -1:
                    return query_end_index, query_end_index
                else:
                    return query_param_start_index, query_end_index
        else:
            return -1, -1

    def substitute_body(self, new_body_blocks):
        """ Substitute the body part in the old request with the new body

        @param old_request: The original request
        @type  old_request: Request
        @param new_body: Request blocks of the new body
        @type  new_body: List

        @return: The new request
        @rtype:  Request or None on failure

        """
        old_request = self
        # substitute the body definition with the new one
        idx = old_request.get_body_start()
        if idx == -1:
            return None

        new_definition = old_request.definition[:idx] + new_body_blocks
        new_definition += [old_request.metadata.copy()]
        new_request = Request(new_definition)
        # Update the new Request object with the create once requests data of the old Request,
        # so bug replay logs will include the necessary create once request data.
        new_request._create_once_requests = old_request._create_once_requests

        # Update the new request with the query and header schemas of the old request, since
        # these must still be present for correctly rendering the request combinations.
        new_request.set_headers_schema(old_request.headers_schema)
        new_request.set_query_schema(old_request.query_schema)
        return new_request

    def substitute_query(self, new_query_blocks):
        """ Substitutes the query portion in the old request with the new queries

        @param old_request: The original request
        @type  old_request: Request
        @param new_query_blocks: Request blocks of the new query
        @type  new_query_blocks: List[str]

        @return: The new request
        @rtype : Request or None on failure

        """
        old_request = self
        start_idx, end_idx = old_request.get_query_start_end()

        if end_idx < 0:
            return None

        # Handle case where there are no query parameters in the default schema.
        # Query parameters can always be added after the path.
        if start_idx == end_idx:
            if new_query_blocks:
                new_query_blocks.insert(0, primitives.restler_static_string('?'))

        # If the new query is empty, remove the '?' if it exists
        if not new_query_blocks and (start_idx != end_idx):
            start_idx = start_idx - 1
        new_definition = old_request.definition[:start_idx] + new_query_blocks + old_request.definition[end_idx:]
        new_definition += [old_request.metadata.copy()]
        new_request = Request(new_definition)
        # Update the new Request object with the create once requests data of the old Request,
        # so bug replay logs will include the necessary create once request data.
        new_request._create_once_requests = old_request._create_once_requests
        return new_request


def GrammarRequestCollection():
    """ Accessor for the global request collection singleton """
    return GlobalRequestCollection.Instance()._req_collection

class GlobalRequestCollection(object):
    __instance = None

    @staticmethod
    def Instance():
        if GlobalRequestCollection.__instance == None:
            raise Exception("Request Collection not yet initialized.")
        return GlobalRequestCollection.__instance

    def __init__(self, req_collection):
        if GlobalRequestCollection.__instance:
            raise Exception("Attempting to create a new singleton instance.")

        self._req_collection = req_collection

        GlobalRequestCollection.__instance = self


class RequestCollection(object):
    """ Collection of Request """
    def __init__(self, requests=[]):
        """ Instantiates a collection of requests.

        @param requests: List of Request class objects.
        @type  requests: List

        """
        if requests:
            # This request constructor should always be empty;
            # the interface exists for compatibility reasons only.
            raise Exception("Attempting to initialize RequestCollection with a pre-defined"
            " list of Request objects. This is not allowed. The interface is in place for"
            " compatibility reasons only.")

        # grammar name (if applicable).
        self._grammar_name = ''

        # Request objects that comprise current sequence
        self._requests = []

        # Groupings of requests with their request ids
        self._request_id_collection = dict()

        # pointer to shared global pool of candidate values
        self.candidate_values_pool = primitives.CandidateValuesPool()

    def __iter__(self):
        """ Iterate over RequestCollection objects. """
        return iter(self._requests)

    def __deepcopy__(self, memo):
        """ Don't deepcopy this object, just return its reference """
        return self

    def _append_request_id(self, request):
        """ Helper function that appends requests to the request_id collection.
        The request ID collection groups Requests by their shared request IDs.
        These request IDs are not unique among Request objects, but can be used
        to identify requests with matching endpoints.

        @param request: The request to append
        @type  request: Request

        @return: None
        @rtype : None

        """
        if request.request_id not in self._request_id_collection:
            self._request_id_collection[request.request_id] = []
        # Add the request to the list of requests with this same request ID
        self._request_id_collection[request.request_id].append(request)

    def update_hosts(self):
        """ Updates the Host fields in each request of the grammar file

        @return: None
        @rtype : None

        """
        for req in self._requests:
            req.update_host()


    def update_basepaths(self):
        """ Updates the basepaths in each request of the grammar file

        @return: None
        @rtype : None

        """
        for req in self._requests:
            req.update_basepath()

    def get_host_from_grammar(self):
        """ Gets the hostname from the grammar

        @return: The hostname or None if not found
        @rtype : Str or None

        """
        for req in self._requests:
            idx = req.get_host_index()
            if idx >= 0:
                return request_utilities.get_hostname_from_line(req._definition[idx][1])
        return None

    def add_request(self, request):
        """ Adds a new request in the collection of requests.

        @param requests: Request to be added in requests collection.
        @type  request: Request class object.

        @return: None
        @rtype : None

        """
        if request._definition not in map(lambda r: r._definition,
                                          self._requests):
            self._requests.append(request)
            self._append_request_id(request)

    def set_grammar_name(self, grammar_name):
        """ Set grammar name (if applicable).

        @param grammar_name: the name of the grammar.
        @type  grammar_name: Str

        @return: None
        @rtype : None

        """
        self._grammar_name = grammar_name

    def set_custom_mutations(self, custom_mutations, per_endpoint_custom_mutations):
        """ Assigns user-defined mutation to pool of mutations.

        @param custom_mutations: The dictionary of user-provided mutations.
        @type  custom_mutations: Dict
        @param per_endpoint_custom_mutations: The per-endpoint custom mutations
        @type  per_endpoint_custom_mutations: Dict

        @return: None
        @rtype : None

        """
        self.candidate_values_pool.set_candidate_values(custom_mutations, per_endpoint_custom_mutations)

    def remove_authentication_tokens(self):
        """ Removes the authentication token line from each request in the collection

        @return: None
        @rtype : None

        """
        for req in self._requests:
            for line in req.definition:
                if line[0] == primitives.REFRESHABLE_AUTHENTICATION_TOKEN:
                    req._definition.remove(line)
                    break

    @property
    def request_id_collection(self):
        """ Returns the request id collection, which is a dictionary of request IDs
        that map to a list of requests with that ID.

        @return: The request id collection
        @rtype : Dict(Int: List[Request])
        """
        return self._request_id_collection

    @property
    def size(self):
        """ Returns the number of requests currently in set.

        @return: The number of request in collection.
        @rtype : Int

        """
        return len(self._requests)
