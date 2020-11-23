# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import itertools
from collections import OrderedDict
import utils.logger as logger
from engine.transport_layer.response import CONNECTION_CLOSED_CODE
from engine.transport_layer.response import TIMEOUT_CODE
from engine.core.request_utilities import str_to_hex_def

class NewSingletonError(Exception):
    pass

class UninitializedError(Exception):
    pass

class BugBucket(object):
    def __init__(self, sequence, reproducible, reproduce_attempts, reproduce_successes):
        self.sequence = sequence
        self.reproducible = reproducible
        self.reproduce_attempts = reproduce_attempts
        self.reproduce_successes = reproduce_successes

class BugBuckets(object):
    __instance = None

    @staticmethod
    def Instance():
        """ Singleton's instance accessor

        @return BugBuckets instance
        @rtype  BugBuckets

        """
        if BugBuckets.__instance == None:
            raise UninitializedError("BugBuckets not yet initialized.")
        return BugBuckets.__instance

    def __init__(self):
        if BugBuckets.__instance:
            raise NewSingletonError("Attempting to create a new singleton instance.")

        self._bug_buckets = dict()
        BugBuckets.__instance = self

    def _ending_request_exists(self, sequence, bug_buckets):
        """ If sequence xB exists we should not add xyB, because xB is already
        good enough.

        @param sequence: The sequence that triggered an error's definition
        @type  sequence: Sequence
        @param bug_buckets: Specific class of buckets (main driver or checker)
        @type  bug_buckets: Dict

        @return: Bool
        @rtype : True if the last request of the sequence already exists in some bucket.

        """
        # Iterate through each sequence in the bug buckets
        for b in bug_buckets.values():
            if b.sequence.last_request.hex_definition == sequence.last_request.hex_definition:
                return True

        return False

    def _get_create_once_requests(self, sequence):
        """ Helper that collects any requests used during a create once
        operation. This is required for the replay log to get populated
        with all of the necessary resource generating requests for this
        sequence.

        The request lists are iterated in order, so simply appending unique
        create-once requests to the list should be sufficient in the cases
        where multiple create once endpoints were used that affect this
        sequence.

        @param sequence: The error sequence to get create once requests for
        @type  sequence: Sequence
        @return: The create once requests list
        @rtype : List[Request
        ]
        """
        create_once_requests = []
        for req in sequence.requests:
            if req.create_once_requests is not None:
                for c_req in req.create_once_requests:
                    if c_req not in create_once_requests:
                        create_once_requests.append(c_req)
        return create_once_requests

    def _get_bucket_origin(self, origin, bug_code):
        """ Helper to get the bug bucket origin string from a bug code

        @param origin: The origin of the bug (checker name, main driver, etc)
        @type  origin: Str
        @param bug_code: The status code that triggered the bug
        @type  bug_code: Str
        @return: The bucket origin
        @rtype : Str

        """
        if bug_code == TIMEOUT_CODE:
            return f'{origin}_timeout'
        elif bug_code == CONNECTION_CLOSED_CODE:
            return f'{origin}_connection_closed'
        elif bug_code.startswith('20'):
            return f'{origin}_20x'
        else:
            return f'{origin}_{bug_code}'

    def _get_bug_hash(self, origin, sequence, hash_full_request, additional_str):
        """ Helper that creates and returns the unique bug hash

        @param origin: The origin of the bug
        @type  origin: Str
        @param sequence: The sequence that triggered the bug
        @type  sequence: Sequence
        @param hash_full_request: If True, use the entire request definition for the hash
        @type  hash_full_request: Boolean
        @param additional_str: Any additional string to be used when creating the hash
        @type  additional_str: Str or None
        @return: The sha1 bug hash
        @rtype : Str

        """
        if hash_full_request:
            request_str = sequence.last_request.hex_definition
        else:
            request_str = sequence.last_request.method_endpoint_hex_definition

        if additional_str is not None:
            request_str += additional_str

        return f'{origin}_{str_to_hex_def(request_str)}'

    def _test_bug_reproducibility(self, sequence, bug_code, bucket):
        """ Helper function that replays a sequence to test whether or not
        a bug can be reproduced.

        @param sequence: The bug sequence to replay
        @type  sequence: Sequence
        @param bug_code: The status code that was received when the bug was identified.
        @type  bug_code: Str
        @param bucket: Pointer to the bug bucket related to this bug
        @type  bucket: OrderedDict - {seq_hex: BugBucket}
        @return: Tuple containing whether the bug was reproduced,
                 the new retry count, and the new reproduced count
        @rtype : Tuple(bool, int, int)

        """
        seq_hex = sequence.hex_definition
        logger.raw_network_logging("Attempting to reproduce bug...")
        status_code = sequence.replay_sequence()
        reproducible = status_code and status_code == bug_code
        logger.raw_network_logging("Done replaying sequence.")
        # Gather reproduce retry counts to apply to bucket
        reproduce_attempts = 1
        reproduce_successes = 0
        first_bug_was_reproducible = reproducible
        if seq_hex in bucket:
            reproduce_attempts = bucket[seq_hex].reproduce_attempts + 1
            reproduce_successes = bucket[seq_hex].reproduce_successes
            if bucket[seq_hex].reproducible == False:
                first_bug_was_reproducible = bucket[seq_hex].reproducible
        reproduce_successes = reproduce_successes + 1 if reproducible else reproduce_successes
        return (first_bug_was_reproducible, reproduce_attempts, reproduce_successes)

    def update_bug_buckets(self, sequence, bug_code, origin='main_driver', reproduce=True, additional_log_str=None, checker_str=None, hash_full_request=False, lock=None):
        """ Update buckets of error-triggering test case buckets by potentially
        adding sequence.

        @param sequence: The sequence that triggered the bug
        @type  sequence: Sequence class object.
        @param bug_code: The status code that triggered the bug
        @type  bug_code: Str
        @param origin: The origin of the bug (checker name, main driver, etc)
        @type  origin: Str
        @param additional_log_str: An optional string that can be added to the bug's replay header
        @type  additional_log_str: Str or None
        @param checker_str: Additional string supplied by certain checkers to be used for creating unique hashes
        @type  checker_str: Str or None
        @param hash_full_request: If True, use the entire request definition for the hash
        @type  hash_full_request: Boolean
        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object or None

        @return: None
        @rtype : None

        Note: Sequences are bucketized using the methodology describes in:
            https://arxiv.org/pdf/1806.09739.pdf (section: 4.5)

        """
        if lock is not None:
            lock.acquire()

        try:
            bucket_origin = self._get_bucket_origin(origin, bug_code)
            if bucket_origin not in self._bug_buckets:
                self._bug_buckets[bucket_origin] = OrderedDict()
            bucket = self._bug_buckets[bucket_origin]
            seq_hex = sequence.hex_definition

            if (seq_hex not in bucket and not self._ending_request_exists(sequence, bucket)) or\
            (reproduce and seq_hex in bucket and bucket[seq_hex].reproducible == False):
                if reproduce:
                    (reproducible, reproduce_attempts, reproduce_successes) = self._test_bug_reproducibility(sequence, bug_code, bucket)
                else:
                    (reproducible, reproduce_attempts, reproduce_successes) = (False, 0, 0)
                bucket[seq_hex] = BugBucket(sequence, reproducible, reproduce_attempts, reproduce_successes)

            sent_request_data_list = sequence.sent_request_data_list
            create_once_requests = self._get_create_once_requests(sequence)
            sent_request_data_list = create_once_requests + sent_request_data_list
            bug_hash = self._get_bug_hash(bucket_origin,sequence,hash_full_request,checker_str)
            logger.update_bug_buckets(self._bug_buckets, sent_request_data_list, bug_hash, additional_log_str=additional_log_str)
        finally:
            if lock is not None:
                lock.release()

    def num_bug_buckets(self, lock=None):
        """ Calculates the total number of bug buckets and the buckets
        per class.

        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object

        @return: Number of requests sent so far.
        @rtype : Dict

        """
        if lock is not None:
            lock.acquire()

        try:
            d = OrderedDict()
            for k in sorted(self._bug_buckets):
                d[k] = len(self._bug_buckets[k])
        finally:
            if lock is not None:
                lock.release()

        return dict(d)
