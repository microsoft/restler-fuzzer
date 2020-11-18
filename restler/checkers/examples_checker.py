# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import copy

from checkers.checker_base import *
from engine.fuzzing_parameters.fuzzing_utils import *
from engine.bug_bucketing import BugBuckets
from engine.core.request_utilities import str_to_hex_def
from engine.core.requests import Request
from engine.core.sequences import Sequence
import engine.primitives as primitives

class ExamplesChecker(CheckerBase):
    """ Checker for payload body fuzzing. """

    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

        # alias the log
        self._log = self._checker_log.checker_print
        # list of requests that have already been tested
        self._tested_requests: set = set()

    def apply(self, rendered_sequence, lock):
        """ Applies check for fuzzing request payload body

        @param rendered_sequence: Object containing the rendered sequence information
        @type  rendered_sequence: RenderedSequence
        @param lock: Lock object used to sync more than one fuzzing job
        @type  lock: thread.Lock

        @return: None
        @type  : None

        """
        if not rendered_sequence.sequence:
            return

        self._sequence = copy.copy(rendered_sequence.sequence)
        last_request = self._sequence.last_request
        # Remove the last request from the sequence list because it will be replaced
        # with new requests.
        self._sequence.requests = self._sequence.requests[:-1]
        self._sequence._sent_request_data_list = self._sequence._sent_request_data_list[:-1]

        last_request_def = str_to_hex_def(last_request.method) + last_request.request_id
        # check to see if we already tested this request
        if last_request_def in self._tested_requests:
            return

        self._tested_requests.add(last_request_def)

        if last_request.examples:
            self._log("Sending examples for request: \n"
                      f"{last_request.endpoint}\n"
                      f"Previous attempt was {'valid' if rendered_sequence.valid else 'invalid'}.")

            self._send_each_example(last_request)

    def _send_each_example(self, request):
        """ Substitutes each example into the request and sends it
        """
        def _send_request(request_to_send):
            self._log("Sending example request: \n"
                      f"{request_to_send.definition}", print_to_network_log=False)
            seq = self._sequence + Sequence(request_to_send)
            response, _ = self._render_and_send_data(seq, request_to_send)

            code = response.status_code
            self._log(f"Status Code: {code}", print_to_network_log=False)
            if code not in status_codes:
                status_codes[code] = 0
            status_codes[code] += 1

            # Check to make sure a bug wasn't uncovered while executing the sequence
            if response and response.has_bug_code():
                self._print_suspect_sequence(seq, response)
                BugBuckets.Instance().update_bug_buckets(seq, code, origin=self.__class__.__name__, hash_full_request=True)

        status_codes = {}

        # Send new request for each body example
        for example in request.examples.body_examples:
            blocks = example.get_blocks()
            new_request = substitute_body(request, blocks)
            if new_request:
                _send_request(new_request)
            else:
                self._log(f"Failed to substitute body for request {request.endpoint}.")
        # Send new request for each query example.
        # For now don't try to match these up with body examples.
        # There will soon be IDs associated with the examples, so they can be matched.
        for example in request.examples.query_examples:
            q_blocks = []
            for idx, query in enumerate(example.queries):
                q_blocks += query.get_blocks()
                if idx < len(example) - 1:
                    # Add the query separator
                    q_blocks.append(primitives.restler_static_string('&'))
            new_request = substitute_query(request, q_blocks)
            if new_request:
                _send_request(new_request)
            else:
                self._log('Failed to substitute query')

        self._log("Results:")
        for code in status_codes:
            self._log(f"{code}: {status_codes[code]}")
        self._log("\n", print_to_network_log=False)

