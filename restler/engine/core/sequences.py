# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Defines restler Sequences. """
from __future__ import print_function

import sys
import copy
import time
import json

import engine.core.async_request_utilities as async_request_utilities
import engine.core.request_utilities as request_utilities
import engine.core.status_codes_monitor as status_codes_monitor

from engine.core.fuzzing_monitor import Monitor
from engine.core.requests import GrammarRequestCollection
from engine.core.requests import FailureInformation
from restler_settings import Settings
from engine.bug_bucketing import BugBuckets
from engine.core.request_utilities import str_to_hex_def
import utils.logger as logger
import engine.dependencies as dependencies
from engine.errors import ResponseParsingException
from engine.errors import TransportLayerException
from engine.errors import TimeOutException
from engine.errors import NoTokenSpecifiedException
from engine.transport_layer.response import RESTLER_INVALID_CODE
from utils.logger import raw_network_logging as RAW_LOGGING
from utils.logger import custom_network_logging as CUSTOM_LOGGING

AUTHORIZATION_TOKEN_PLACEHOLDER = 'AUTHORIZATION TOKEN'

class SentRequestData(object):
    """ SentRequestData class """
    def __init__(self, rendered_data, parser, response="", producer_timing_delay=0, max_async_wait_time=0):
        self.rendered_data = rendered_data
        self.parser = parser
        self.response = response
        self.producer_timing_delay = producer_timing_delay
        self.max_async_wait_time = max_async_wait_time

class RenderedSequence(object):
    """ RenderedSequence class """
    def __init__(self, sequence=None, valid=False, failure_info=None, final_request_response=None):
        """ Initializes RenderedSequence object

        @param sequence: The sequence that was rendered
        @type  sequence: Sequence or None if not rendered
        @param valid: True if this was a valid rendering
        @type  valid: Bool
        @param failure_info: Information about an invalid rendering
        @type  failure_info: FailureInformation
        @param final_request_response: The response received from the final request in the sequence
        @type  final_request_response: HttpResponse

        """
        self.sequence = sequence
        self.valid = valid
        self.failure_info = failure_info
        self.final_request_response = final_request_response

class Sequence(object):
    """ Implements basic sequence logic.  """
    def __init__(self, requests=None):
        """ Instantiates a sequence given a list of request objects.

        @param requests: The list of request that comprise current sequence.
        @type  requests: List of Request class objects.

        @return: None
        @rtype : None

        """
        if requests is None:
            requests = []
        # The position of this sequence in a sequence collection.
        # This is used during logging.
        self.seq_i = 0
        self.requests = list(requests)
        # A list of all requests in this sequence that were sent;
        # as the exact data that was rendered and set to the server
        self._sent_request_data_list = []

    def __iter__(self):
        """ Iterate over Sequences objects. """
        return iter(self.requests)

    def __add__(self, other):
        """ Add two sequnces

        @return: None
        @rtype : None

        """
        new_seq = Sequence(self.requests + other.requests)
        new_seq.seq_i = self.seq_i
        new_seq._sent_request_data_list = self._sent_request_data_list + other._sent_request_data_list
        return new_seq

    def __copy__(self):
        """ Shallow copy of Sequence object

        @return: new copy of this Sequence
        @rtype : Sequence

        """
        new_seq = Sequence(self.requests)
        new_seq.seq_i = self.seq_i
        new_seq._sent_request_data_list = list(self._sent_request_data_list)
        return new_seq

    @property
    def consumes(self):
        """ Returns all of the dynamic objects consumed by the requests in this Sequence

        @return: The dynamic objects consumed by this Sequence
        @rtype : List

        """
        return [req.consumes for req in self.requests]

    @property
    def produces(self):
        """ Returns all of the dynamic objects produced by the reuqests in this Sequence

        @return: The dynamic objects produced by this Sequence
        @rtype : List

        """
        return [req.produces for req in self.requests]

    @property
    def definition(self):
        """ Iterable list representation of definitions of requests of sequence.

        @return: Requests' definition in list representation.
        @rtype : List

        """
        seq_definition = []
        for request in self.requests:
            seq_definition.append(request.definition)
        return seq_definition

    @property
    def hex_definition(self):
        """ Hex representation of sequence's definition.

        @return: Hex representation of sequence's definition.
        @rtype : Str

        """
        seq_hex_definition = []
        for request in self.requests:
            seq_hex_definition.append(request.hex_definition)

        return str_to_hex_def("".join(seq_hex_definition))

    @property
    def last_request(self):
        """ Gets the final request in this sequence

        @return: The final request in this sequence
        @rtype : Request

        """
        return self.requests[-1]

    @property
    def length(self):
        """ Return sequence length.

        @return: The length (number of requests) of the current sequence.
        @rtype : Int

        """
        return len(self.requests)

    @property
    def sent_request_data_list(self):
        """ Returns the sent data list. The rendered_data represents the
        actual request string that was sent to the server after the
        dependencies were resolved and dynamic object values were populated.
        This information can be used to identify the exact values used for
        dynamic variables or to re-send the requests.

        Note: The data is expected to be sent through sendRecv in
        messaging.py to populate the header properly. Also,
        the authorization token will need to be populated prior to
        sending the request. See get_request_data_with_token().

        @return: The sent request data list
        @rtype : List[SentRequestData]

        """
        return self._sent_request_data_list

    def has_destructor(self):
        """ Helper to decide whether the current sequence instance contains any
        request which is a destructor.

        @return: True, if the current sequence contains any destructor.
        @rtype : Bool

        """
        for request in self.requests:
            if request.is_destructor():
                return True
        return False

    def is_empty_sequence(self):
        """ Helper to decide if current sequence is empty.

        @return: True, if current sequence is empty.
        @rtype : Bool

        """
        return not self.requests

    def resolve_dependencies(self, data):
        """ Renders dependent variables.

        @param data: The rendered payload with dependency placeholders.
        @type data: String

        @return: The rendered payload with dependency placeholders substituted
                    by the respective values parsed from the appropriate
                    responses.
        @rtype : String

        """
        data = str(data).split(dependencies.RDELIM)
        for i in range(1, len(data), 2):
            var_name = data[i]
            data[i] = dependencies.get_variable(var_name)
            if data[i] == 'None':
                RAW_LOGGING(f'Dynamic object {var_name} is set to None!')
        return "".join(data)

    def render(self, candidate_values_pool, lock, preprocessing=False, postprocessing=False):
        """ Core routine that performs the rendering of restler sequences. In
        principal all requests of a sequence are being constantly rendered with
        a specific values combination @param request._current_combination_id
        which we know in the past led to a valid rendering and only the last
        request of the sequence is being rendered iteratively with all feasible
        value combinations. Each time a "valid rendering" is found for the last
        request of the sequence (where "valid rendering" is defined according
        to "VALID_CODES"), the routine returns a new sequence which has an
        end-to-end (i.e., all requests) "valid rendering" and can be added in
        the sequences collection in order to be used in the future as a building
        block for longer sequences.


        @param candidate_values_pool: The pool of values for primitive types.
        @type candidate_values_pool: Dict
        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object
        @param preprocessing: Set to true if rendering during preprocessing
        @type  preprocessing: Bool

        @return: A RenderedSequence object containing the sequence, the final
                 request's response, whether or not the final request received
                 a valid status code, and a FailureInformation enum if there was
                 a failure or bug detected during rendering.
        @rtype : RenderedSequence
        """
        # Try rendering  all primitive type value combinations for last request
        request = self.last_request

        # for clarity reasons, don't log requests whose render iterator is over
        if request._current_combination_id <\
                request.num_combinations(candidate_values_pool):
            CUSTOM_LOGGING(self, candidate_values_pool)

        self._sent_request_data_list = []
        for rendered_data, parser in\
                request.render_iter(candidate_values_pool,
                                    skip=request._current_combination_id,
                                    preprocessing=preprocessing):
            # Hold the lock (because other workers may be rendering the same
            # request) and check whether the current rendering is known from the
            # past to lead to invalid status codes. If so, skip the current
            # rendering.
            if lock is not None:
                lock.acquire()
            should_skip = Monitor().is_invalid_rendering(request)
            if lock is not None:
                lock.release()

            # Skip the loop and don't forget to increase the counter.
            if should_skip:
                RAW_LOGGING("Skipping rendering: {}".\
                            format(request._current_combination_id))
                request._current_combination_id += 1
                continue

            # Clean up internal state
            self.status_codes = []
            dependencies.reset_tlb()

            sequence_failed = False
            # Step A: Static template rendering
            # Render last known valid combination of primitive type values
            # for every request until the last
            for i in range(len(self.requests) - 1):
                prev_request = self.requests[i]
                prev_rendered_data, prev_parser =\
                    prev_request.render_current(candidate_values_pool,
                    preprocessing=preprocessing)

                # substitute reference placeholders with resolved values
                if not Settings().ignore_dependencies:
                    prev_rendered_data =\
                        self.resolve_dependencies(prev_rendered_data)

                prev_req_async_wait = Settings().get_max_async_resource_creation_time(prev_request.request_id)
                prev_producer_timing_delay = Settings().get_producer_timing_delay(prev_request.request_id)

                prev_response = request_utilities.send_request_data(prev_rendered_data)
                prev_response_to_parse, resource_error, async_waited = async_request_utilities.try_async_poll(
                    prev_rendered_data, prev_response, prev_req_async_wait)
                prev_parser_threw_exception = False
                # Response may not exist if there was an error sending the request or a timeout
                if prev_parser and prev_response_to_parse:
                    prev_parser_threw_exception = not request_utilities.call_response_parser(prev_parser, prev_response_to_parse, prev_request)
                prev_status_code = prev_response.status_code

                # If the async logic waited for the resource, this wait already included the required
                # producer timing delay. Here, set the producer timing delay to zero, so this wait is
                # skipped both below for this request and during replay
                if async_waited:
                    prev_producer_timing_delay = 0
                else:
                    prev_req_async_wait = 0

                self.append_data_to_sent_list(prev_rendered_data, prev_parser, prev_response, prev_producer_timing_delay, prev_req_async_wait)

                if not prev_status_code:
                    logger.write_to_main(f"Error: Failed to get status code during valid sequence re-rendering.\n")
                    sequence_failed = True
                    break

                if prev_response.has_bug_code():
                    BugBuckets.Instance().update_bug_buckets(
                        self, prev_status_code, reproduce=False, lock=lock)
                    sequence_failed = True
                    break

                if prev_parser_threw_exception:
                    logger.write_to_main("Error: Parser exception occurred during valid sequence re-rendering.\n")
                    sequence_failed = True
                    break

                if resource_error:
                   logger.write_to_main("Error: The resource was left in a Failed state after creation during valid sequence re-rendering.\n")
                   sequence_failed = True
                   break

                # If the previous request is a resource generator and we did not perform an async resource
                # creation wait, then wait for the specified duration in order for the backend to have a
                # chance to create the resource.
                if prev_producer_timing_delay > 0 and prev_request.is_resource_generator():
                    print(f"Pausing for {prev_producer_timing_delay} seconds, request is a generator...")
                    time.sleep(prev_producer_timing_delay)

                # register latest client/server interaction
                timestamp_micro = int(time.time()*10**6)
                self.status_codes.append(status_codes_monitor.RequestExecutionStatus(timestamp_micro,
                                                                prev_request.hex_definition,
                                                                prev_status_code,
                                                                prev_response.has_valid_code(),
                                                                False))

            if sequence_failed:
                self.status_codes.append(
                    status_codes_monitor.RequestExecutionStatus(
                        int(time.time()*10**6),
                        request.hex_definition,
                        RESTLER_INVALID_CODE,
                        False,
                        True
                    )
                )
                Monitor().update_status_codes_monitor(self, self.status_codes, lock)
                return RenderedSequence(failure_info=FailureInformation.SEQUENCE)

            # Step B: Dynamic template rendering
            # substitute reference placeholders with ressoved values
            # for the last request
            if not Settings().ignore_dependencies:
                rendered_data = self.resolve_dependencies(rendered_data)

            # Render candidate value combinations seeking for valid error codes
            request._current_combination_id += 1

            req_async_wait = Settings().get_max_async_resource_creation_time(request.request_id)

            response = request_utilities.send_request_data(rendered_data)
            response_to_parse, resource_error, _ = async_request_utilities.try_async_poll(
                rendered_data, response, req_async_wait)
            parser_exception_occurred = False
            # Response may not exist if there was an error sending the request or a timeout
            if parser and response_to_parse:
                parser_exception_occurred = not request_utilities.call_response_parser(parser, response_to_parse, request)
            status_code = response.status_code
            if not status_code:
                return RenderedSequence(None)

            self.append_data_to_sent_list(rendered_data, parser, response, max_async_wait_time=req_async_wait)

            rendering_is_valid = not parser_exception_occurred\
                and not resource_error\
                and response.has_valid_code()
            # register latest client/server interaction and add to the status codes list
            timestamp_micro = int(time.time()*10**6)
            self.status_codes.append(status_codes_monitor.RequestExecutionStatus(timestamp_micro,
                                                                     request.hex_definition,
                                                                     status_code,
                                                                     rendering_is_valid,
                                                                     False))

            # add sequence's error codes to bug buckets.
            if response.has_bug_code():
                BugBuckets.Instance().update_bug_buckets(
                    self, status_code, lock=lock
                )

            Monitor().update_status_codes_monitor(self, self.status_codes, lock)

            # Register current rendering's status.
            if lock is not None:
                lock.acquire()
            Monitor().update_renderings_monitor(request, rendering_is_valid)
            if lock is not None:
                lock.release()

            if Monitor().remaining_time_budget <= 0 and not postprocessing:
                raise TimeOutException("Exceeded Timeout")

            if lock is not None:
                lock.acquire()
            # Deep  copying here will try copying anything the class has access
            # to including the shared client monitor, which we update in the
            # above code block holding the lock, but then we release the
            # lock and one thread can be updating while another is copying.
            # This is a typlical nasty read after write syncronization bug.
            duplicate = copy.deepcopy(self)
            if lock is not None:
                lock.release()

            # return a rendered clone if response indicates a valid status code
            if rendering_is_valid or Settings().ignore_feedback:
                return RenderedSequence(duplicate, valid=True, final_request_response=response)
            else:
                information = None
                if response.has_valid_code():
                    if parser_exception_occurred:
                        information = FailureInformation.PARSER
                    elif resource_error:
                        information = FailureInformation.RESOURCE_CREATION
                elif response.has_bug_code():
                    information = FailureInformation.BUG
                return RenderedSequence(duplicate, valid=False, failure_info=information, final_request_response=response)

        return RenderedSequence(None)

    def append_data_to_sent_list(self, rendered_data, parser, response, producer_timing_delay=0, max_async_wait_time=0):
        """ Appends rendered data to the sent-request-data list.

        @param rendered_data: A request's rendered data. This is a data string whose
                              dependencies are resolved and is ready to be sent to the
                              server
        @type  rendered_data: Str
        @param parser: The parser for responses of this request
        @type  parser: Func
        @param response: The response that the request received from the server
        @type  response: Str

        @return: None
        @rtype : None

        """
        rendered_data = request_utilities.replace_auth_token(rendered_data, f'{AUTHORIZATION_TOKEN_PLACEHOLDER}')
        self._sent_request_data_list.append(
            SentRequestData(
                rendered_data, parser, response.to_str, producer_timing_delay, max_async_wait_time
            )
        )

    def replace_last_sent_request_data(self, rendered_data, parser, response, producer_timing_delay=0, max_async_wait_time=0):
        """ Replaces the final sent request with new rendered data

        @param rendered_data: A request's rendered data. This is a data string whose
                              dependencies are resolved and is ready to be sent to the
                              server
        @type  rendered_data: Str
        @param parser: The parser for responses of this request
        @type  parser: Func
        @param response: The response that the request received from the server
        @type  response: Str

        @return: None
        @rtype : None

        """
        self._sent_request_data_list = self._sent_request_data_list[:-1]
        self.append_data_to_sent_list(rendered_data, parser, response, producer_timing_delay, max_async_wait_time)

    def get_request_data_with_token(self, data):
        """ Returns an updated request data string with the appropriate authorization token

        @param data: Request data with AUTHORIZATION TOKEN that needs to be updated
        @type  data: Str

        @return: The rendered data with the correct token
        @rtype : Str

        """
        rendered_data = data
        if AUTHORIZATION_TOKEN_PLACEHOLDER in data:
            token = request_utilities.get_latest_token_value()
            if token == request_utilities.NO_TOKEN_SPECIFIED:
                raise NoTokenSpecifiedException
            rendered_data = data.replace(
                f"{AUTHORIZATION_TOKEN_PLACEHOLDER}\r\n", token
            )
        return rendered_data

    def set_sent_requests_for_replay(self, sent_request_data_list):
        """ Sets the sent request data list. Will overwrite any request
        data that already exists in the sent request data list.

        @param sent_request_data_list: The sent request data to set
        @type  sent_request_data_list: List[SentRequestData]

        @return: None
        @rtype : None

        """
        self._sent_request_data_list = sent_request_data_list

    def replay_sequence(self):
        """ Replays the previously rendered data belonging to this sequence.

        Each time this sequence is rendered, each of its request's rendered
        data is saved to a list, which is then replayed, using this function,
        exactly as it was the first time (using the same dynamic object values)

        @return: The status code produced by the final request (or None for failure)
        @rtype : Str

        """
        def send_and_parse(request_data):
            """ Gets the token, sends the requst, performs async wait, parses response, returns status code """
            rendered_data = self.get_request_data_with_token(request_data.rendered_data)
            response = request_utilities.send_request_data(rendered_data)
            response_to_parse, _, _ = async_request_utilities.try_async_poll(
                rendered_data, response, request_data.max_async_wait_time)
            if request_data.parser:
                request_utilities.call_response_parser(request_data.parser, response_to_parse)
            return response.status_code

        # Send all but the last request in the sequence
        for request_data in self._sent_request_data_list[:-1]:
            rendered_data = self.get_request_data_with_token(request_data.rendered_data)
            if not send_and_parse(request_data):
                return None
            if request_data.producer_timing_delay > 0:
                print(f"Pausing for {request_data.producer_timing_delay} seconds, request is a generator...")
                time.sleep(request_data.producer_timing_delay)

        final_request_data = self._sent_request_data_list[-1]
        # Send final request and return its status code
        return send_and_parse(final_request_data)
