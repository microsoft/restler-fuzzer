# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Tracks each request rendering with information on whether it is valid or invalid """
class RenderingsMonitor(object):
    def __init__(self):
       # Keeps track of the current generation being fuzzed by the driver.
        self._current_fuzzing_generation = 0

        # client-side monitor of valid rendering ids for each request
        self._rendering_ids = {}

        self._memoize_invalid_past_renderings = False


    def update(self, request, is_valid):
        """ Updates internal request rendering tracker with information on
        whether the current rendering is valid or invalid.

        @param request: The request whose current rendering we are registering.
        @type  request: Request class object.
        @param is_valid: Flag indicating whether the current rendering leads to
                            a valid status code or not.
        @type  is_valid: Bool

        @return: None
        @rtype : None

        Note: The "minus one" rendering because the counter has been increased
            before invoking this routine.
        """
        if self._current_fuzzing_generation not in self._rendering_ids:
            self._rendering_ids[self._current_fuzzing_generation] = {}

        renderings = self._rendering_ids[self._current_fuzzing_generation]
        if request.hex_definition not in renderings:
            renderings[request.hex_definition] = {'valid': set(),
                                                  'invalid': set()}

        target = 'valid' if is_valid else 'invalid'
        renderings[request.hex_definition][target].add(
            request._current_combination_id - 1
        )

    def reset(self):
        """ Resets the renderings monitor.
        This is used specifically to reset the monitor after
        proprocessing and prior to starting the fuzzing run.

        @return: None
        @rtype : None

        """
        self._rendering_ids.clear()

    def is_invalid_rendering(self, request):
        """ Helper to decide whether current request's rendering is registered
        in the past with an invalid status code.

        @param request: The request whose current rendering we are registering.
        @type  request: Request class object.

        @return: True, if rendering is known invalid.
        @rtype : Bool

        Note: In order to be sure that we could skip a rendering it must have
        completed a whole round of the previous generation having only invalid
        renderings and no valid. (Consider the fact that the same rendering of
        a request may have both valid and invalid renderings.)

        Note: This function is called with the lock HELD.

        """
        # If option is not set, do not skip anything.
        if not self._memoize_invalid_past_renderings:
            return False

        # If request has not completed a whole round of the previous generation,
        # do not skip
        if self._current_fuzzing_generation - 1 not in self._rendering_ids:
            return False

        renderings = self._rendering_ids[self._current_fuzzing_generation - 1]
        req_hex = request.hex_definition
        if req_hex not in renderings:
            return False

        # If request has completed previous generation and ONLY has invalid
        # renderings, the skip.
        invalid = renderings[req_hex]['invalid']
        valid = renderings[req_hex]['valid']
        return request._current_combination_id in invalid - valid

    def is_fully_rendered_request(self, request, lock):
        """ Queries internal monitor to decide if the @param request has ever
        been rendered by the driver. Note that for a request to have been
        rendered it means that in the past it had had its dependencies satisfied
        within some sequence.

        @param request: The request in question.
        @type  request: Request class object.
        @param lock: Lock object used for sync of more than one fuzzing jobs.
        @type  lock: thread.Lock object

        @return: True if the request in question has been rendered in the past.
        @rtype : Bool

        """
        if lock is not None:
            lock.acquire()

        # If request has not completed a whole round of the previous generation,
        # do not skip
        if self._current_fuzzing_generation - 1 not in self._rendering_ids:
            if lock is not None:
                lock.release()
            return False

        for generation in range(0, self._current_fuzzing_generation):
            renderings = self._rendering_ids[generation]
            req_hex = request.hex_definition
            result = req_hex in renderings
            if result:
                break

        if lock is not None:
            lock.release()
        return result

    def num_fully_rendered_requests(self, request_list, lock):
        """ Queries internal monitor and returns the total number of requests
        (of request collection) that have been rendered at least once
        (regardless of the status code with which the target service responded).

        @param request_list: The complete list of requests to check for full renderings
        @type  request_list: List[Request]

        @return: The number of requests that have been rendered at least once.
        @rtype : Int

        """
        counter = 0
        for request in request_list:
            if self.is_fully_rendered_request(request, lock):
                counter += 1
        return counter

    def set_memoize_invalid_past_renderings_on(self):
        """ Internal sets feature for skipping known invalid past renderings.

        @return: None
        @rype  : None

        """
        self._memoize_invalid_past_renderings = True

    @property
    def current_fuzzing_generation(self):
        return self._current_fuzzing_generation

    @current_fuzzing_generation.setter
    def current_fuzzing_generation(self, generation):
        self._current_fuzzing_generation = generation

