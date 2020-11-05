# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Implements logic for leakage rule checker. """
from __future__ import print_function

from checkers.checker_base import *

import time
import itertools

from engine.bug_bucketing import BugBuckets
import engine.dependencies as dependencies
import engine.core.sequences as sequences

class LeakageRuleChecker(CheckerBase):
    """ Checker for resource leakage violations. """
    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

    def apply(self, rendered_sequence, lock):
        """ Applies check for leakage rule violations.

        @param rendered_sequence: Object containing the rendered sequence information
        @type  rendered_sequence: RenderedSequence
        @param lock: Lock object used to sync more than one fuzzing job
        @type  lock: thread.Lock

        @return: None
        @rtype : None

        """
        # Note that, unlike other checkers, the precondition here is failed renderings.
        if rendered_sequence.valid:
            return
        # Return if the sequence was never fully rendered
        if rendered_sequence.sequence is None:
            return
        self._sequence = rendered_sequence.sequence

        # We skip any sequence that contains DELETE methods so that we
        # keep in isolation this checker and the use-after-free checker.
        if self._sequence.has_destructor():
            return

        # Type produced by the sequence. Necessary for type-checking
        produces = self._sequence.produces
        seq_produced_types = set(itertools.chain(*produces))

        # Target the types produced by the last request of the sequence.
        target_types = produces[-1]

        for target_type in target_types:
            self._checker_log.checker_print(f"\nTarget type: {target_type}")
            # Iterate through each request that has a matching request ID to the the final
            # request in the sequence, which is the request that will be checked for leakage.
            for req in self._req_collection.request_id_collection[self._sequence.last_request.request_id]:
                # Skip requests that are not consumers or don't type-check.
                if not req.consumes\
                    or req.consumes - seq_produced_types\
                    or target_type not in req.consumes:
                        continue

                self._set_dynamic_variables(self._sequence.sent_request_data_list[-1].rendered_data, req)
                self._render_consumer_request(self._sequence + sequences.Sequence(req))

                if self._mode != 'exhaustive':
                    break

    def _set_dynamic_variables(self, sent_data, request):
        """ Helper that sets dynamic variables to the values that a failed request
        was attempting to produce.

        @param sent_data: The data from the sent request
        @type  sent_data: Str
        @param request: A request that consumes the dynamic variable from the sent
                        request. This is used to find the location of the dynamic
                        variables within the @param sent_data string
        @type  request: Request

        @return: None
        @rtype : None

        """
        # Get sent data endpoint
        sent_data = sent_data.split(" HTTP")[0]
        sent_data = sent_data.split("?")[0]
        # Split sent data and request endpoint data to try and find dependencies, Ex:
        # sent_data = PUT somevar/A-1234/someothervar/B-5678/
        # sent_split = [PUT somevar, A-1234, someothervar, B-5678]
        # placeholder_split = [PUT somevar, _READER_DELIM_A_READER_DELIM_, someothervar, _READER_DELIM_A_READER_DELIM_]
        sent_split = sent_data.split('/')
        placeholder_split = request.endpoint.split('/')

        # Iterate through the request endpoint and set the dynamic variables with the matching
        # values that were sent in the request that triggered this checker
        for index, val in enumerate(placeholder_split):
            if dependencies.RDELIM in val:
                dependencies.set_variable_no_gc(val.replace(dependencies.RDELIM, ""), sent_split[index])

    def _render_consumer_request(self, seq):
        """ Render the last request of the sequence and inspect the status
        code of the response. If it's not 40x, we have probably hit a bug.

        @param seq: The sequence whose last request we will try to render.
        @type  seq: Sequence Class object.

        @return: None
        @rtype : None

        """
        request = seq.last_request
        response, _ = self._render_and_send_data(seq, request)
        if response and self._rule_violation(seq, response):
            self._print_suspect_sequence(seq, response)
            BugBuckets.Instance().update_bug_buckets(seq, response.status_code, origin=self.__class__.__name__)

    def _false_alarm(self, seq, response):
        """ Catches leakage rule violation false alarms that occur when
        a DELETE request receives a 204 as a response status_code

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
