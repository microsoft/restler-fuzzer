# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" A simple demo checker that reports a bug. """
from __future__ import print_function

from checkers.checker_base import *

from engine.bug_bucketing import BugBuckets
import engine.core.sequences as sequences
from engine.errors import TimeOutException
import engine.dependencies as dependencies

class DemoChecker(CheckerBase):
    """ A simple checker that runs after every request, and reports 2 bugs. """
    # Dictionary used for determining whether a request has already
    # been sent for the current generation.
    # { generation : set(request.hex_definitions) }
    generation_executed_requests = dict()

    # Keep track of how many bugs were reported
    # For demo purposes only
    bugs_reported = 0

    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

    def apply(self, rendered_sequence, lock):
        """ Fuzzes each value in the parameters of this request as specified by
        the custom dictionary and settings for this checker.

        @param rendered_sequence: Object containing the rendered sequence information
        @type  rendered_sequence: RenderedSequence
        @param lock: Lock object used to sync more than one fuzzing job
        @type  lock: thread.Lock

        @return: None
        @rtype : None

        """
        if not rendered_sequence.sequence:
            return

        # This needs to be set for the base implementation that executes the sequence.
        self._sequence = rendered_sequence.sequence

        last_request = self._sequence.last_request
        generation = self._sequence.length

        self._checker_log.checker_print(f"Testing request: {last_request.endpoint} {last_request.method}")

        # Just run this checker once for the endpoint and method
        # If all schema combinations are desired, use 'last_request.hex_definition' instead below
        request_hash = last_request.method_endpoint_hex_definition
        if DemoChecker.generation_executed_requests.get(generation) is None:
            # This is the first time this checker has seen this generation, create empty set of requests
            DemoChecker.generation_executed_requests[generation] = set()
        elif request_hash in DemoChecker.generation_executed_requests[generation]:
            # This request type has already been tested for this generation
            return
        # Add the last request to the generation_executed_requests dictionary for this generation
        DemoChecker.generation_executed_requests[generation].add(request_hash)

        # Set up pre-requisites required to run the request
        # The code below sets up the state and re-executes the requests on which this request depends on.
        req_async_wait = Settings().get_max_async_resource_creation_time(last_request.request_id)
        new_seq = self._execute_start_of_sequence()

        # Add the last request of the sequence to the new sequence
        checked_seq = new_seq + sequences.Sequence(last_request)
        # Add the sent prefix requests for replay
        checked_seq.set_sent_requests_for_replay(new_seq.sent_request_data_list)
        # Create a placeholder sent data, so it can be replaced below when bugs are detected for replays
        checked_seq.append_data_to_sent_list("GET /", None,  HttpResponse(), max_async_wait_time=req_async_wait)

        # Render the current request combination
        rendered_data, parser, tracked_parameters, updated_writer_variables = \
            next(last_request.render_iter(self._req_collection.candidate_values_pool,
                                          skip=last_request._current_combination_id - 1,
                                          preprocessing=False))

        # Resolve dependencies
        if not Settings().ignore_dependencies:
            rendered_data = checked_seq.resolve_dependencies(rendered_data)

        # Exit if time budget exceeded
        if Monitor().remaining_time_budget <= 0:
            raise TimeOutException('Exceed Timeout')

        # Send the request and get a response
        response = request_utilities.send_request_data(rendered_data)
        if response.has_valid_code():
            for name,v in updated_writer_variables.items():
                dependencies.set_variable(name, v)

        responses_to_parse, resource_error, _ = async_request_utilities.try_async_poll(
            rendered_data, response, req_async_wait)

        # Response may not exist if there was an error sending the request or a timeout
        if parser and responses_to_parse:
            # The response parser must be invoked so that dynamic objects created by this
            # request are initialized, adding them to the list of objects for the GC to clean up.
            parser_exception_occurred = not request_utilities.call_response_parser(parser, None,
                                                                                   request=last_request,
                                                                                   responses=responses_to_parse)

        if response and self._rule_violation(checked_seq, response, valid_response_is_violation=True):
            checked_seq.replace_last_sent_request_data(rendered_data, parser, response, max_async_wait_time=req_async_wait)
            self._print_suspect_sequence(checked_seq, response)
            BugBuckets.Instance().update_bug_buckets(checked_seq, response.status_code, origin=self.__class__.__name__)
            self.bugs_reported += 1

        self._checker_log.checker_print(f"Tested request"
                                        f"{last_request.endpoint} {last_request.method}, combination "
                                        f"{last_request._current_combination_id}.")

    def _false_alarm(self, seq, response):
        """ For demo purposes, returns 'True' if more than 2 requests were tested by this checker.
        This causes at most 2 bugs to be reported by this checker.

        @param seq: The sequence that contains the request with the rule violation
        @type  seq: Sequence
        @param response: Body of response.
        @type  response: Str

        @return: True if false alarm detected
        @rtype : Bool

        """
        return self.bugs_reported == 2
