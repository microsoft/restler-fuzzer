# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Implements logic for resource hierarchy rule checker. """
from __future__ import print_function

from checkers.checker_base import *
import itertools

from engine.bug_bucketing import BugBuckets
import engine.dependencies as dependencies
import engine.core.sequences as sequences

class ResourceHierarchyChecker(CheckerBase):
    """ Checker for ResourceHierarchy rule violations. """
    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

    def apply(self, rendered_sequence, lock):
        """ Applies check for resource hierarchy rule violations.

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

        # We skip any sequence that contains DELETE methods so that we
        # keep in isolation this checker and the use-after-free checker.
        if self._sequence.has_destructor():
            return

        consumes = self._sequence.consumes
        predecessors_types = consumes[:-1]
        # Last request is the victim -- our target!
        target_types = consumes[-1]
        # In the dictionary of "consumes" constraints, each request of the
        # sequence instance has its own dictionary of the dynamic variable
        # types produced by each request. We need to flatten this structure.
        predecessors_types = set(itertools.chain(*predecessors_types))

        # Skip sequence if there are no predecessor dependencies or no
        # target objects to swap.
        if not predecessors_types.intersection(target_types)\
                or not target_types - predecessors_types:
            return

        # For the victim types (target dynamic objects), get the lattest
        # values which we know will exist due to the previous rendering.
        # We will later on use these old values atop a new rendering.
        old_values = {}
        for target_type in target_types - predecessors_types:
           old_values[target_type] = dependencies.get_variable(target_type)

        # Reset tlb of all values and re-render all predecessor up to
        # the parent's parent. This will propagate new values for all
        # dynamic objects except for those with target type. That's what we
        # want and that's why we render up to the parent's parent (i.e.,
        # up to length(seq) - 2.
        dependencies.reset_tlb()

        # Render sequence up to before the first predecessor that produces
        # the target type. that is, if any of the types produced by the
        # request is in the target types, then do not render this
        # predecessor and stop here.
        n_predecessors =  0
        for req in self._sequence:
            if req.produces.intersection(target_types - predecessors_types):
                break
            n_predecessors += 1
        new_seq = self._render_n_predecessor_requests(n_predecessors)

        # log some helpful info
        self._checker_log.checker_print("\nTarget types: {}".\
                            format(target_types - predecessors_types))
        self._checker_log.checker_print(f"Predecesor types: {predecessors_types}")
        self._checker_log.checker_print("Clean tlb: {}".\
                            format(dependencies.tlb))

        # Before rendering the last request, substitute all target types
        # (target dynamic object) with a value that does NOT belong to
        # the current rendering and should not (?) be accessible through
        # the new predecessors' rendering.
        for target_type in old_values:
            dependencies.set_variable(target_type, old_values[target_type])

        self._checker_log.checker_print("Poluted tlb: {}".\
                            format(dependencies.tlb))
        self._render_last_request(new_seq)

    def _render_n_predecessor_requests(self, n_predecessors):
        """ Render up to the parent's parent predecessor request.

        @param n_predecessors: The number of predecessors to render.
        @type  n_predecessors: Int

        @return: Sequence of n predecessor requests sent to server
        @rtype : Sequence

        """
        new_seq = sequences.Sequence([])
        for i in range(n_predecessors):
            request = self._sequence.requests[i]
            new_seq = new_seq + sequences.Sequence(request)
            response, _ = self._render_and_send_data(new_seq, request)
            # Check to make sure a bug wasn't uncovered while executing the sequence
            if response and response.has_bug_code():
                self._print_suspect_sequence(new_seq, response)
                BugBuckets.Instance().update_bug_buckets(new_seq, response.status_code, origin=self.__class__.__name__)

        return new_seq

    def _render_last_request(self, new_seq):
        """ Render the last request of the sequence and inspect the status
        code of the response. If it's any of 20x, we have probably hit a bug.

        @param new_seq: The new sequence that was rendered with this checker
        @type  new_seq: Sequence

        @return: None
        @rtype : None

        """
        new_seq = new_seq + sequences.Sequence(self._sequence.last_request)
        response, _ = self._render_and_send_data(new_seq, self._sequence.last_request)
        if response and self._rule_violation(new_seq, response):
            self._print_suspect_sequence(new_seq, response)
            BugBuckets.Instance().update_bug_buckets(new_seq, response.status_code, origin=self.__class__.__name__)
