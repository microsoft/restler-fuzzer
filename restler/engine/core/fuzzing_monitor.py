# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Global monitor for the fuzzing run """
import time

from engine.core.status_codes_monitor import StatusCodesMonitor
from engine.core.renderings_monitor import RenderingsMonitor

def Monitor():
    """ Accessor for the FuzzingMonitor singleton """
    return FuzzingMonitor.Instance()

class FuzzingMonitor(object):
    __instance = None

    @staticmethod
    def Instance():
        """ Singleton's instance accessor

        @return FuzzingMonitor instance
        @rtype  FuzzingMonitor

        """
        if FuzzingMonitor.__instance == None:
            raise Exception("FuzzingMonitor not yet initialized.")
        return FuzzingMonitor.__instance

    def __init__(self):
        if FuzzingMonitor.__instance:
            raise Exception("Attempting to create a new singleton instance.")

        # timestamp of the beginning of fuzzing session
        self._start_time = int(time.time()*10**6)

        # time budget to stop fuzzing jobs (time in hours)
        self._time_budget = 24*30 # (~ 1 month)

        # Create the status codes monitor
        self.status_codes_monitor = StatusCodesMonitor(self._start_time)
        # Create the renderings monitor
        self.renderings_monitor = RenderingsMonitor()

        FuzzingMonitor.__instance = self


    def set_time_budget(self, time_in_hours):
        """ Set the initial time budget.

        @param time_in_hours: Time budget in hours.
        @type  time_in_hours: Int

        @return: None
        @rtype : None

        """
        self._time_budget = 10**6*3600*float(time_in_hours)

    def reset_start_time(self):
        """ Resets start time to now (time of routine's invocation in
            microseconds).

        @return: None
        @rtype : None

        """
        self._start_time = int(time.time()*10**6)
        self.status_codes_monitor._start_time = self._start_time


    @property
    def running_time(self):
        """ Returns the running time.

        @return: Running time in microseconds.
        @rtype : int

        """
        _running_time = int(time.time()*10**6) - self._start_time
        return _running_time

    @property
    def remaining_time_budget(self):
        """ Returns the time remaining from the initial budget.

        @return: Remaining time in microseconds.
        @rtype : int

        """
        running_time = int(time.time()*10**6) - self._start_time
        return self._time_budget - running_time

    @property
    def start_time(self):
        """ Returns start time of fuzzing.

        @return: The start time in seconds.
        @rtype : int

        """
        return self._start_time

    def terminate_fuzzing(self):
        """ Terminates the fuzzing thread by setting the time budget to zero

        @return: None
        @rtype : None

        """
        self._time_budget = 0.0

    ## Start of RenderingsMonitor functions
    def update_renderings_monitor(self, request, is_valid):
        """ Calls the renderings monitor's update function

        @param request: The request whose current rendering we are registering.
        @type  request: Request class object.
        @param is_valid: Flag indicating whether the current rendering leads to
                         a valid status code or not.
        @type  is_valid: Bool

        @return: None
        @rtype : None

        """
        self.renderings_monitor.update(request, is_valid)

    def reset_renderings_monitor(self):
        """ Calls internal renderings monitor's reset function

        @return: None
        @rtype : None

        """
        self.renderings_monitor.reset()

    def is_invalid_rendering(self, request):
        """ Calls internal renderings monitor's is_invalid_rendering function

        @param request: The request whose current rendering we are registering.
        @type  request: Request class object.

        @return: True, if rendering is known invalid.
        @rtype : Bool

        """
        return self.renderings_monitor.is_invalid_rendering(request)

    def is_fully_rendered_request(self, request, lock=None):
        """ Calls internal renderings monitor's is_fully_rendered_request function

        @param request: The request in question.
        @type  request: Request class object.
        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object

        @return: True if the request in question has been rendered in the past.
        @rtype : Bool

        """
        return self.renderings_monitor.is_fully_rendered_request(request, lock)

    def num_fully_rendered_requests(self, request_list, lock=None):
        """ Calls internal renderings monitor's num_fully_rendered_requests function

        @param request_list: The complete list of requests to check for full renderings
        @type  request_list: List[Request]

        @return: The number of requests that have been rendered at least once.
        @rtype : Int

        """
        return self.renderings_monitor.num_fully_rendered_requests(request_list, lock)

    def set_memoize_invalid_past_renderings_on(self):
        """ Calls internal renderings monitor's set_memoize_invalid_past_renderings_on functino

        @return: None
        @rtype : None

        """
        self.renderings_monitor.set_memoize_invalid_past_renderings_on()

    @property
    def current_fuzzing_generation(self):
        """ Returns the current fuzzing generation

        @return: The current fuzzing generation
        @rtype : Int

        """
        return self.renderings_monitor.current_fuzzing_generation

    @current_fuzzing_generation.setter
    def current_fuzzing_generation(self, generation):
        """ Setter for the current fuzzing generation

        @param generation: The new generation to set
        @type  generation: Int

        @return: None
        @rtype : None

        """
        self.renderings_monitor.current_fuzzing_generation = generation

    # Start of StatusCodeMonitor functions
    def increment_requests_count(self, type):
        """ Calls internal status codes monitor's increment_requests_count function

        @param type: The type of request count to increment (i.e. gc)
        @type  type: Str

        @return: None
        @rtype : None

        """
        self.status_codes_monitor.increment_requests_count(type)

    def num_requests_sent(self):
        """ Calls internal status codes monitor's num_requests_sent function

        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type lock: thread.Lock object

        @return: Number of requests sent so far.
        @rtype : Dict

        """
        return self.status_codes_monitor.num_requests_sent()

    def num_test_cases(self, lock=None):
        """ Calls internal status codes monitor's num_test_cases function

        DEPRECATED: This function is currently deprecated and unused

        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type lock: thread.Lock object

        @return: Number of test cases executed so far.
        @rtype : Int

        """
        return self.status_codes_monitor.num_test_cases(lock)

    def query_status_codes_monitor(self, request, valid_codes, fail_codes, lock=None):
        """ Calls internal status codes monitor's query_response_codes function

        @param request: The request in question.
        @type  request: Request class object.
        @param valid_codes: List of status codes to query for.
        @type  valid_codes: List[str]
        @param fail_codes: List of failure status codes to query for.
        @type  fail_codes: List[str]
        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object

        @return: A namedtuple object, which contains:
                 whether or not the status code was valid, the request was fully valid,
                 and if the request failed due to a failed sequence re-render
        @rtype : Namedtuple(valid_code, fully_valid, sequence_failure)

        """
        return self.status_codes_monitor.query_response_codes(request, valid_codes, fail_codes, lock)

    def update_status_codes_monitor(self, sequence, status_codes, lock=None):
        """ Calls internal status codes monitor's update function

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

        """
        self.status_codes_monitor.update(sequence, status_codes, lock)

    @property
    def sequence_statuses(self):
        """ Returns a copy of the status codoes monitor's sequence_statuses dictionary

        @return A copy of the sequence_statuses dictionary
        @rtype Dict(int, SequenceStatusCodes)

        """
        return self.status_codes_monitor.sequence_statuses
