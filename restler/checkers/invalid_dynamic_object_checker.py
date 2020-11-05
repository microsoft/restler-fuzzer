# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Implements logic for invalid dynamic object checker. """
from __future__ import print_function

from checkers.checker_base import *
import time
import uuid

from engine.bug_bucketing import BugBuckets
import engine.dependencies as dependencies
import engine.core.sequences as sequences
from utils.logger import raw_network_logging as RAW_LOGGING

class InvalidDynamicObjectChecker(CheckerBase):
    """ Checker for invalid dynamic object violations. """
    # Dictionary used for determining whether or not a request has already
    # been sent for the current generation.
    # { generation : set(request.hex_definitions) }
    generation_executed_requests = dict()

    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

    def apply(self, rendered_sequence, lock):
        """ Applies check for invalid dynamic object rule violations.

        @param rendered_sequence: Object containing the rendered sequence information
        @type  rendered_sequence: RenderedSequence
        @param lock: Lock object used to sync more than one fuzzing job
        @type  lock: thread.Lock

        @return: None
        @rtype : None

        """
        if not rendered_sequence.valid:
            return

        self._sequence = rendered_sequence.sequence
        last_request = self._sequence.last_request

        # If the last request is not a consumer then this checker is not applicable
        if not last_request.consumes:
            return

        generation = self._sequence.length

        if InvalidDynamicObjectChecker.generation_executed_requests.get(generation) is None:
            # This is the first time this checker has seen this generation, create empty set of requests
            InvalidDynamicObjectChecker.generation_executed_requests[generation] = set()
        elif last_request.hex_definition in InvalidDynamicObjectChecker.generation_executed_requests[generation]:
            # This request type has already been tested for this generation
            return

        # Add the last request to the generation_executed_requests dictionary for this generation
        InvalidDynamicObjectChecker.generation_executed_requests[generation].add(last_request.hex_definition)

        # Get the current rendering of the sequence, which will be the valid rendering of the last request
        last_rendering, last_request_parser = last_request.render_current(self._req_collection.candidate_values_pool)

        # Execute the sequence up until the last request
        new_seq = self._execute_start_of_sequence()
        # Add the last request of the sequence to the new sequence
        new_seq = new_seq + sequences.Sequence(last_request)

        # Get and send each invalid request
        self._checker_log.checker_print("\nSending invalid request(s):")
        for data in self._prepare_invalid_requests(last_rendering):
            self._checker_log.checker_print(repr(data))
            response = self._send_request(last_request_parser, data)
            request_utilities.call_response_parser(last_request_parser, response)
            if response and self._rule_violation(new_seq, response):
                # Append the data that we just sent to the sequence's sent list
                new_seq.append_data_to_sent_list(data, last_request_parser, response)
                BugBuckets.Instance().update_bug_buckets(new_seq, response.status_code, origin=self.__class__.__name__)
                self._print_suspect_sequence(new_seq, response)


    def _execute_start_of_sequence(self):
        """ Send all requests in the sequence up until the last request

        @return: Sequence of n predecessor requests send to server
        @rtype : Sequence

        """
        RAW_LOGGING("Re-rendering and sending start of sequence")
        new_seq = sequences.Sequence([])
        for request in self._sequence.requests[:-1]:
            new_seq = new_seq + sequences.Sequence(request)
            response, _ = self._render_and_send_data(new_seq, request)
            # Check to make sure a bug wasn't uncovered while executing the sequence
            if response and response.has_bug_code():
                self._print_suspect_sequence(new_seq, response)
                BugBuckets.Instance().update_bug_buckets(new_seq, response.status_code, origin=self.__class__.__name__)

        return new_seq

    def _prepare_invalid_requests(self, data):
        """ Prepares requests with invalid dynamic objects.
        Each combination of valid/invalid for requests with multiple
        objects will be prepared

        @param data: The rendered payload with dependency placeholders.
        @type data: String

        @return: Each request rendered
        @rtype : Generator of strings

        """
        # If this string is found in an invalid object string, replace it with
        # the actual valid dynamic object.
        # Example: valid object = name123, invalid object string = VALID_REPLACE_STR/?/,
        # new invalid object string = name123/?/
        VALID_REPLACE_STR = 'valid-object'

        RAW_LOGGING("Preparing requests with invalid objects")
        # Split data string into the following format:
        # [0] = start_of_data, [1] = dependency, [2] = data_until_next_dependency
        # [3] = dependency (if more exist), [4] = data_until_next_dependency ...
        data = str(data).split(dependencies.RDELIM)

        consumer_types = []
        # Save off the valid dependencies.
        # Iterate through data list; starting at first dependency and skipping
        # to each subsequent dependency
        for i in range(1, len(data), 2):
            consumer_types.append(dependencies.get_variable(data[i]))

        default_invalids = [f'{VALID_REPLACE_STR}?injected_query_string=123',\
                            f'{VALID_REPLACE_STR}/?/',\
                            f'{VALID_REPLACE_STR}??',\
                            f'{VALID_REPLACE_STR}/{VALID_REPLACE_STR}',\
                            '{}']

        invalid_strs = []
        if not Settings().get_checker_arg(self._friendly_name, 'no_defaults'):
            invalid_strs = default_invalids

        user_invalids = Settings().get_checker_arg(self._friendly_name, 'invalid_objects')
        if isinstance(user_invalids, list):
            # Add the default checks
            invalid_strs.extend(user_invalids)

        for invalid_str in invalid_strs:
            # Iterate through every possible combination (2^n) of invalid/valid objects
            # Stop before the last combination (all valid)
            for valid_mask in range(2**len(consumer_types) - 1):
                index = 0
                for i in range(1, len(data), 2):
                    if ((valid_mask >> index) & 1):
                        # Set valid object to the previously saved variable
                        data[i] = consumer_types[index]
                    else:
                        data[i] = invalid_str.replace(VALID_REPLACE_STR, consumer_types[index])
                    index = index + 1
                yield "".join(data)

    def _false_alarm(self, seq, response):
        """ Catches invalid dynamic object rule violation false alarms that
        occur when a DELETE request receives a 204 as a response status_code

        @param seq: The sequence that contains the request with the rule violation
        @type  seq: Sequence
        @param response: Body of response.
        @type  response: Str

        @return: True if false alarm detected
        @rtype : Bool

        """
        try:
            # If a DELETE request was sent and the status code returned was a 204,
            # we can assume that this was not a failure because many services use a 204
            # response code when there is nothing to delete
            return response.status_code.startswith("204")\
                and seq.last_request.method.startswith('DELETE')
        except Exception:
            return False
