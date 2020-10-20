# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Maintains a collection of status codes received by each sequence """
import time
import collections

class RequestExecutionStatus(object):
    """ RequestExecutionStatus class. """
    def __init__(self, timestamp, request_hex, status_code, is_fully_valid, sequence_failure, num_test_cases=0):
        """ Initializes the RequestExecutionStatus object

        @param timestamp: The timestamp of the request
        @type  timestamp: Int
        @param request_hex: The corresponding Request object's hex definition
        @type  request_hex: Int
        @param status_code: The status code returned after sending the request
        @type  status_code: Str
        @param is_fully_valid: If the request received a fully-valid response
        @type  is_fully_valid: Bool
        @param sequence_failure: If the sequence failed before the request was completed
        @type  sequence_failure: Bool
        @param num_test_cases:
        @type  num_test_cases: Int

        @return: None
        @rtype : None

        """
        self.timestamp = timestamp
        self.request_hex = request_hex
        self.status_code = status_code
        self.is_fully_valid = is_fully_valid
        self.sequence_failure = sequence_failure
        self.num_test_cases = num_test_cases

class SequenceStatusCodes(object):
    """ Collection of status codes for a sequence """
    def __init__(self, length):
        self.length = length
        # Contains list of RequestExecutionStatus objects with status codes as keys
        self.request_statuses = dict()

class StatusCodesMonitor(object):
    def __init__(self, start_time):
        # The start time of the fuzzing run
        self._start_time = start_time

        # Counter of total requests sent by each type
        self._requests_count = {'gc': 0, 'main_driver': 0}

        # Collection of SequenceStatusCodes objects with sequence hex defs as keys
        self._sequence_statuses = dict()

        # stuff for experiments with GitLab
        self.log_counter = 1

    @property
    def sequence_statuses(self):
        """ Returns a copy of the sequence_statuses dictionary

        @return A copy of the sequence_statuses dictionary
        @rtype Dict(int, SequenceStatusCodes)

        """
        return dict(self._sequence_statuses)

    def increment_requests_count(self, type):
        """ Increments the requests count for a specified request type

        @param type: The type of request count to increment (i.e. gc)
        @type  type: Str

        @return: None
        @rtype : None

        """
        if type not in self._requests_count:
            self._requests_count[type] = 0
        self._requests_count[type] += 1

    def num_requests_sent(self):
        """ Returns a copy of the dict containing the request count for
        each type.

        @return: The number of requests sent for each type
        @rtype : Dict

        """
        return dict(self._requests_count)

    def num_test_cases(self, lock=None):
        """ Calculates the total number of test cases executed so far. Locking
        may be required in case of more than one fuzzing jobs.

        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object

        @return: Number of test cases executed so far.
        @rtype : Int

        """
        if lock is not None:
            lock.acquire()

        total_size = 0
        for seq_hash in self._sequence_statuses:
            timestamps = []
            for code in self._sequence_statuses[seq_hash].request_statuses:
                timestamps.extend(self._sequence_statuses[seq_hash].request_statuses[code])
            total_size += len(timestamps) / self._sequence_statuses[seq_hash].length

        if lock is not None:
            lock.release()

        return total_size

    def query_response_codes(self, request, status_codes, fail_codes, lock):
        """ Query internal monitor to decide if @param request had received any
        of @param status_codes as a service response.

        @param request: The request in question.
        @type  request: Request class object.
        @param status_codes: List of status codes to query for.
        @type  status_codes: List
        @param fail_codes: List of failing status codes to query for.
        @type  fail_codes: List
        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object

        @return: A namedtuple object, which contains:
                 whether or not the status code was valid, the request was fully valid,
                 and if the request failed due to a failed sequence re-render
        @rtype : Namedtuple(valid_code, fully_valid, sequence_failure)

        """
        if lock is not None:
            lock.acquire()

        QueryResult = collections.namedtuple('QueryResult', ['valid_code', 'fully_valid', 'sequence_failure'])
        for seq_hash in self._sequence_statuses:
            # iterate over each status code that was detected in this sequence
            for code in self._sequence_statuses[seq_hash].request_statuses:
                if code in status_codes or code in fail_codes:
                    for req in self._sequence_statuses[seq_hash].request_statuses[code]:
                        # Check if the request exists for this status code
                        if request.hex_definition == req.request_hex:
                            if lock is not None:
                                lock.release()
                            if code in status_codes:
                                valid_code = True
                            else:
                                valid_code = False
                            return QueryResult(valid_code, req.is_fully_valid, req.sequence_failure)

        if lock is not None:
            lock.release()
        return QueryResult(valid_code=False, fully_valid=False, sequence_failure=False)

    def update(self, sequence, status_codes, lock):
        """ Updates the internal monitor with status codes received.

        @param sequence: The sequence which was just executed and whose status
                           codes going to be registered in the internal monitor.
        @type  sequence: Sequence class object.
        @param status_codes: List of RequestExecutionStatus objects used when updating
                            the status codes monitor
        @type  status_codes: List[RequestExecutionStatus]
        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object

        @return: None
        @rtype : None

        Note: Most of this function's book-keeping is for plotting.

        """
        if lock is not None:
            lock.acquire()

        seq_length = sequence.length
        self._requests_count['main_driver'] += seq_length
        seq_definition = sequence.definition
        seq_hash = sequence.hex_definition

        if seq_hash not in self._sequence_statuses:
            self._sequence_statuses[seq_hash] = SequenceStatusCodes(seq_length)

        # keep counter before looping over a changing dictionary
        num_test_cases = self.num_test_cases() +  1
        for code in status_codes:
            relative_timestamp = code.timestamp - self._start_time
            if code.status_code not in self._sequence_statuses[seq_hash].request_statuses:
                self._sequence_statuses[seq_hash].request_statuses[code.status_code] = []
            new_req_status = RequestExecutionStatus(
                relative_timestamp, code.request_hex, code.status_code, code.is_fully_valid, code.sequence_failure, num_test_cases=num_test_cases)
            self._sequence_statuses[seq_hash].request_statuses[code.status_code].append(new_req_status)

        running_time = int((int(time.time()*10**6) - self._start_time)/ 10**6)
        INTERVAL = 10 # minutes
        if running_time > self.log_counter*INTERVAL*60:
            from utils import logger
            logger.copy_stats(self.log_counter)
            self.log_counter += 1

        if lock is not None:
            lock.release()

