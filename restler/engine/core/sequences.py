# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Defines restler Sequences. """
from __future__ import print_function

import sys
import copy
import time
import json
import datetime
from enum import Enum

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
from utils.logging.trace_db import SequenceTracker

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
    def __init__(self, sequence=None, valid=False, failure_info=None, final_request_response=None,
                 response_datetime=None):
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
        self.final_response_datetime = response_datetime

class RenderedPrefixStatus(Enum):
    NONE = 1
    VALID = 2
    INVALID = 3

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
        # Indicates whether the prefix of this sequence has been rendered.
        # If so, the dynamic objects created in the prefix have been saved, and
        # must be freed when the sequence has finished rendering.
        self.rendered_prefix_status = RenderedPrefixStatus.NONE

        # Indicates that this sequence should only render its prefix once.
        self.create_prefix_once = False
        # If a cached sequence prefix is present, indicates that this sequence
        # should re-render it after a valid sequence rendering.
        self.re_render_prefix_on_success = None

        self.executed_requests_count = 0

        self._used_cached_prefix = False

    def __iter__(self):
        """ Iterate over Sequences objects. """
        return iter(self.requests)

    def __add__(self, other):
        """ Add two sequences

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


    @property
    def methods_endpoints_hex_definition(self):
        """ Returns the concatenation of the method_endpoint_hex_definitions
            of requests in this Sequence

        @return: A string describing the unique ID by method and endpoint for this sequence
        @rtype : str
        """
        hex_definition_ids = [ f"{req.method_endpoint_hex_definition}" for req in self.requests ]
        return "_".join(hex_definition_ids)

    @property
    def current_combination_id(self):
        """ Returns the concatenation of the current combination IDs
            of requests in this Sequence

        @return: A string describing the unique combination ID for this sequence
        @rtype : str
        """
        combination_ids = [ f"{req.method_endpoint_hex_definition}_{str(req._current_combination_id)}" \
                            for req in self.requests ]
        return combination_ids

    @property
    def prefix(self):
        """ Returns the longest prefix of this sequence, which contains all
            requests except the last request.

        @return: The prefix sequence
        @rtype : Sequence
        """
        if len(self.requests) < 1:
            return Sequence([])
        return Sequence(self.requests[:-1])

    @property
    def prefix_combination_id(self):
        """ Returns the concatenation of combination IDs, excluding the last request.

        @return: A string describing the unique combination ID for the prefix of this sequence
        @rtype : str
        """
        prefix_ids = [ f"{str(req._current_combination_id)}" for req in self.requests[:-1] ]
        return "_".join(prefix_ids)

    @property
    def combination_id(self):
        """ Returns the concatenation of combination IDs, including the last request.

        @return: A string describing the unique combination ID for this sequence
        @rtype : str
        """
        return "_".join(self.current_combination_id)

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

        @param data: The rendered payload (or list of rendered payload elements)
                     corresponding to the request definition,
                     with dependency placeholders.
        @type data: Str or List[Str]

        @return: The rendered payload (or list of elements) with dependency placeholders substituted
                    by the respective values parsed from the appropriate
                    responses.
        @rtype : String

        """
        if isinstance(data, list):
            for idx, val in enumerate(data):
                if dependencies.RDELIM in val:
                    var_name = str(val).replace(dependencies.RDELIM, '')
                    data[idx] = dependencies.get_variable(var_name)
                    if data[idx] == 'None':
                        RAW_LOGGING(f'Dynamic object {var_name} is set to None!')
            return data
        else:
            data = str(data).split(dependencies.RDELIM)
            for i in range(1, len(data), 2):
                var_name = data[i]
                data[i] = dependencies.get_variable(var_name)
                if data[i] == 'None':
                    RAW_LOGGING(f'Dynamic object {var_name} is set to None!')
            return "".join(data)

    def render(self, candidate_values_pool, lock, preprocessing=False, postprocessing=False):
        """ Core routine that performs the rendering of restler sequences. In
        principle, all requests of a sequence are being constantly rendered with
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

        def render_prefix():
            """
            Renders the last known valid combination of the prefix of this sequence.
            Depending on user settings, this may either be re-rendered for every
            sequence or only once prior to rendering all of the request combinations
            for the last request.

            """
            if self.create_prefix_once and self.rendered_prefix_status == RenderedPrefixStatus.VALID:
                self._used_cached_prefix = True
                return None, None

            self._used_cached_prefix = False
            last_req = self.requests[-1]

            self.create_prefix_once, self.re_render_prefix_on_success = Settings().get_cached_prefix_request_settings(last_req.endpoint_no_dynamic_objects, last_req.method)

            # Clean up internal state
            self.status_codes = []
            dependencies.reset_tlb()
            dependencies.clear_saved_local_dyn_objects()
            dependencies.start_saving_local_dyn_objects()

            sequence_failed = False

            current_request = None
            prev_request = None
            prev_response = None
            response_datetime_str = None
            for i in range(len(self.requests) - 1):
                last_tested_request_idx = i
                prev_request = self.requests[i]
                prev_rendered_data, prev_parser, tracked_parameters, updated_writer_variables =\
                    prev_request.render_current(candidate_values_pool,
                    preprocessing=preprocessing, use_last_cached_rendering=True)

                request.update_tracked_parameters(tracked_parameters)

                # substitute reference placeholders with resolved values
                if not Settings().ignore_dependencies:
                    prev_rendered_data =\
                        self.resolve_dependencies(prev_rendered_data)

                prev_req_async_wait = Settings().get_max_async_resource_creation_time(prev_request.request_id)
                prev_producer_timing_delay = Settings().get_producer_timing_delay(prev_request.request_id)

                SequenceTracker.initialize_request_trace(combination_id=self.combination_id,
                                                         request_id=request.hex_definition)

                prev_response = request_utilities.send_request_data(prev_rendered_data)
                if prev_response.has_valid_code():
                    for name,v in updated_writer_variables.items():
                        dependencies.set_variable(name, v)

                prev_responses_to_parse, resource_error, async_waited = async_request_utilities.try_async_poll(
                    prev_rendered_data, prev_response, prev_req_async_wait)
                prev_parser_threw_exception = False
                # Response may not exist if there was an error sending the request or a timeout
                if prev_parser and prev_responses_to_parse:
                    prev_parser_threw_exception = not request_utilities.call_response_parser(prev_parser, None, request=prev_request, responses=prev_responses_to_parse)
                prev_status_code = prev_response.status_code

                # If the async logic waited for the resource, this wait already included the required
                # producer timing delay. Here, set the producer timing delay to zero, so this wait is
                # skipped both below for this request and during replay
                if async_waited:
                    prev_producer_timing_delay = 0
                else:
                    prev_req_async_wait = 0

                self.append_data_to_sent_list(prev_rendered_data, prev_parser, prev_response, prev_producer_timing_delay, prev_req_async_wait)
                SequenceTracker.clear_request_trace(combination_id=self.combination_id)

                # Record the time at which the response was received
                datetime_now = datetime.datetime.now(datetime.timezone.utc)
                response_datetime_str = datetime_now.strftime(datetime_format)
                timestamp_micro = int(datetime_now.timestamp()*10**6)

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

                rendering_is_valid = not prev_parser_threw_exception\
                    and not resource_error\
                    and prev_response.has_valid_code()

                if not rendering_is_valid:
                   logger.write_to_main("Error: Invalid rendering occurred during valid sequence re-rendering.\n")
                   sequence_failed = True
                   break

                # If the previous request is a resource generator and we did not perform an async resource
                # creation wait, then wait for the specified duration in order for the backend to have a
                # chance to create the resource.
                if prev_producer_timing_delay > 0 and prev_request.is_resource_generator():
                    print(f"Pausing for {prev_producer_timing_delay} seconds, request is a generator...")
                    time.sleep(prev_producer_timing_delay)

                # register latest client/server interaction
                self.status_codes.append(status_codes_monitor.RequestExecutionStatus(timestamp_micro,
                                                                prev_request.hex_definition,
                                                                prev_status_code,
                                                                prev_response.has_valid_code(),
                                                                False))

            self.rendered_prefix_status = RenderedPrefixStatus.INVALID if sequence_failed else RenderedPrefixStatus.VALID
            if sequence_failed:
                self.status_codes.append(
                    status_codes_monitor.RequestExecutionStatus(
                        timestamp_micro,
                        request.hex_definition,
                        RESTLER_INVALID_CODE,
                        False,
                        True
                    )
                )
                Monitor().update_status_codes_monitor(self, self.status_codes, lock)

            self.executed_requests_count = len(self.requests) - 1
            return prev_response, response_datetime_str


        def copy_self():
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
            return duplicate

        request = self.last_request

        # for clarity reasons, don't log requests whose render iterator is over
        if request._current_combination_id <\
                request.num_combinations(candidate_values_pool):
            CUSTOM_LOGGING(self, candidate_values_pool)

        self._sent_request_data_list = []

        datetime_format = "%Y-%m-%d %H:%M:%S"
        response_datetime_str = None
        timestamp_micro = None
        for rendered_data, parser, tracked_parameters, updated_writer_variables in\
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

            # Render candidate value combinations seeking for valid error codes
            request._current_combination_id += 1
            SequenceTracker.initialize_sequence_trace(combination_id=self.combination_id,
                                                      tags={'hex_definition': self.hex_definition})

            request._tracked_parameters = {}
            request.update_tracked_parameters(tracked_parameters)

            # Step A: Static template rendering
            # Render last known valid combination of primitive type values
            # for every request until the last
            try:
                self.executed_requests_count = 0
                prev_response, response_datetime_str = render_prefix()
            finally:
                dependencies.stop_saving_local_dyn_objects()


            if self.rendered_prefix_status == RenderedPrefixStatus.INVALID:
                # A failure to re-render a previously successful sequence prefix may be a
                # transient issue.  Reset the prefix state so it is re-rendered again
                # for the next combination.
                self.rendered_prefix_status = RenderedPrefixStatus.NONE

                duplicate = copy_self()
                return RenderedSequence(duplicate, valid=False, failure_info=FailureInformation.SEQUENCE,
                                        final_request_response=prev_response,
                                        response_datetime=response_datetime_str)

            # Step B: Dynamic template rendering
            # substitute reference placeholders with resolved values
            # for the last request
            if not Settings().ignore_dependencies:
                rendered_data = self.resolve_dependencies(rendered_data)

            req_async_wait = Settings().get_max_async_resource_creation_time(request.request_id)
            req_producer_timing_delay = Settings().get_producer_timing_delay(request.request_id)
            SequenceTracker.initialize_request_trace(combination_id=self.combination_id,
                                                     request_id=request.hex_definition)

            response = request_utilities.send_request_data(rendered_data)
            if response.has_valid_code():
                for name,v in updated_writer_variables.items():
                    dependencies.set_variable(name, v)

            responses_to_parse, resource_error, async_waited = async_request_utilities.try_async_poll(
                rendered_data, response, req_async_wait)
            parser_exception_occurred = False

            # If the async logic waited for the resource, this wait already included the required
            # producer timing delay. Here, set the producer timing delay to zero, so this wait is
            # skipped both below for this request and during replay
            if async_waited:
                req_producer_timing_delay = 0
            else:
                req_async_wait = 0

            # If the request is a resource generator and we did not perform an async resource
            # creation wait, then wait for the specified duration in order for the backend to have a
            # chance to create the resource.
            # One case where this is important is if the garbage collector cannot delete the resource
            # because it is still in a 'creating' state.

            if req_producer_timing_delay > 0 and request.is_resource_generator():
                print(f"Pausing for {req_producer_timing_delay} seconds, request is a generator...")
                time.sleep(req_producer_timing_delay)

            # Response may not exist if there was an error sending the request or a timeout
            if parser and responses_to_parse:
                parser_exception_occurred = not request_utilities.call_response_parser(parser, None, request=request, responses=responses_to_parse)
            status_code = response.status_code

            self.append_data_to_sent_list(rendered_data, parser, response,
                                          producer_timing_delay=req_producer_timing_delay,
                                          max_async_wait_time=req_async_wait)
            self.executed_requests_count = self.executed_requests_count + 1
            SequenceTracker.clear_sequence_trace()

            if not status_code:
                duplicate = copy_self()
                return RenderedSequence(duplicate, valid=False,
                                        failure_info=FailureInformation.MISSING_STATUS_CODE,
                                        final_request_response=response)


            rendering_is_valid = not parser_exception_occurred\
                and not resource_error\
                and response.has_valid_code()

            # Record the time at which the response was received
            datetime_now = datetime.datetime.now(datetime.timezone.utc)
            response_datetime_str=datetime_now.strftime(datetime_format)
            timestamp_micro = int(datetime_now.timestamp()*10**6)

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
            # This is a typical nasty read after write syncronization bug.
            duplicate = copy.deepcopy(self)
            if lock is not None:
                lock.release()

            # Free the dynamic objects from a saved prefix sequence if the request succeeded and
            # the prefix should be re-rendered for the next combination.
            if self.rendered_prefix_status is not None:
                if rendering_is_valid and self.re_render_prefix_on_success == True:
                    self.rendered_prefix_status = None
                    dependencies.stop_saving_local_dyn_objects(reset=True)

            # return a rendered clone if response indicates a valid status code
            if rendering_is_valid or Settings().ignore_feedback:
                return RenderedSequence(duplicate, valid=True, final_request_response=response,
                                        response_datetime=response_datetime_str)
            else:
                information = None
                if response.has_valid_code():
                    if parser_exception_occurred:
                        information = FailureInformation.PARSER
                    elif resource_error:
                        information = FailureInformation.RESOURCE_CREATION
                elif response.has_bug_code():
                    information = FailureInformation.BUG
                return RenderedSequence(duplicate, valid=False, failure_info=information,
                                        final_request_response=response,
                                        response_datetime=response_datetime_str)

        # Since all of the renderings have been tested, clear the rendered prefix status
        # and release local dynamic objects, since they are no longer needed.
        self.rendered_prefix_status = RenderedPrefixStatus.NONE
        dependencies.clear_saved_local_dyn_objects()
        SequenceTracker.clear_sequence_trace()

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
            response = request_utilities.send_request_data(rendered_data, reconnect=True)
            responses_to_parse, _, _ = async_request_utilities.try_async_poll(
                rendered_data, response, request_data.max_async_wait_time)
            if request_data.parser:
                request_utilities.call_response_parser(request_data.parser, None, responses=responses_to_parse)
            return response.status_code

        # TODO: when replaying from the trace DB is supported, the combination ID should be available, since
        # the sequence object will be available.  It may also be useful to provide the original combination ID
        # for the sequence, so that the replay can be associated with the original rendering.
        SequenceTracker.initialize_sequence_trace(None, tags={'origin': 'replay'})

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
        status_code = send_and_parse(final_request_data)
        SequenceTracker.clear_sequence_trace()
        return status_code

class RenderedSequenceCache(object):
    """ Implements a cache of rendered sequences. """
    def __init__(self):
        """ Creates an empty cache
        @return: None
        @rtype : None
        """
        self._cache = {}

    def __get_req_cache(self, sequence):
        last_request = sequence.last_request
        generation = sequence.length
        if generation not in self._cache:
            self._cache[generation] = {}
        generation_cache = self._cache[generation]
        if last_request.method_endpoint_hex_definition not in generation_cache:
            generation_cache[last_request.method_endpoint_hex_definition] = {}

        return generation_cache[last_request.method_endpoint_hex_definition]

    def __get_seq_cache(self, sequence):
        req_cache = self.__get_req_cache(sequence)

        seq_id = sequence.methods_endpoints_hex_definition
        if seq_id not in req_cache:
            req_cache[seq_id] = {True: [], False: []}

        return req_cache[seq_id]

    def add(self, sequence, valid):
        """ Adds sequence to the cache.

        @param sequence:
               The sequence to add.
        @type  Sequence
        @param valid:
               Whether it is a valid rendering.
        @type  bool

        @return: None
        @rtype : None
        """
        if not isinstance(sequence, Sequence):
            raise Exception("Sequences must be used for this cache.")

        seq_cache = self.__get_seq_cache(sequence)

        # only add the sequence if it's not already present
        combination_ids = [req._current_combination_id for req in sequence.requests]

        if combination_ids not in seq_cache[valid]:
            seq_cache[valid].append(combination_ids)

    def add_valid_prefixes(self, sequence):
        """ Adds all the prefixes of the rendered sequence, if
        they are not already cached.

        @param sequence:
               The rendered sequence.
        @type  Sequence

        @return: None
        @rtype : None
        """
        if not isinstance(sequence, Sequence):
            raise Exception("Sequences must be used for this cache.")

        self.add(sequence, True)

        for idx in range(len(sequence.requests[0:-1])):
            prefix_seq = Sequence(sequence.requests[0:idx+1])
            self.add(prefix_seq, True)

    def add_invalid_sequence(self, sequence):
        """ Adds a single invalid rendered sequence to the cache.

        @param sequence:
               The rendered invalid sequence.
        @type  Sequence

        @return: None
        @rtype : None
        """
        if not isinstance(sequence, Sequence):
            raise Exception("Sequences must be used for this cache.")

        self.add(sequence, False)

    def get_prefix(self, req_list, get_all_renderings=False):
        """ Check whether the cache contains a prefix of the requests in
        the specified list.  Returns the rendering ids of the longest found prefix,
        if they exist.

        @param req_list:
               The list of requests whose prefixes should be searched for.
        @type  List
        @param get_all_renderings:
               Whether a single rendering or all renderings should be returned.
        @type  bool

        @return: The list of rendered sequences for the longest prefix found in the cache, and whether each is valid or invalid.
        @rtype : List[Sequence], bool
        """
        found_prefix = False
        for seq_len in range(len(req_list), 0, -1):
            prefix_seq = Sequence(req_list[0:seq_len])
            seq_cache = self.__get_seq_cache(prefix_seq)

            for valid in [True, False]:
                for rendered_sequence_id in seq_cache[valid]:
                    found_prefix = True
                    yield (rendered_sequence_id, valid)
                    if found_prefix and not get_all_renderings:
                        break
                # Exit once the valid renderings of the longest prefix ending in this request are returned.
                if found_prefix:
                    break
            if found_prefix:
                break

    def get_renderings(self, req_list, get_all_renderings=False):
        """ This function takes a list of requests, and returns
        the list of renderings for the longest found prefix already rendered.
        """
        renderings={}

        for prev_combination, valid in self.get_prefix(req_list, get_all_renderings):
            new_seq = Sequence(req_list[:len(prev_combination)])
            new_seq = copy.deepcopy(new_seq)

            for idx, req in enumerate(new_seq.requests):
                req._current_combination_id = prev_combination[idx]

            if valid not in renderings:
                renderings[valid] = []
            # Return the new sequence and the length of the prefix found
            renderings[valid].append(new_seq)

        return renderings

