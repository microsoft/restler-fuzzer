# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" A collection of only the requests that fuzzing will be performed on """
from __future__ import print_function
import time
import engine.core.requests

import engine.primitives as primitives

class FuzzingRequestCollection(object):
    def __init__(self):
        # Reference to Request objects that will be fuzzed
        self._requests = []
        # Set of requests that will be processed during pre or post-processing
        # These requests will not be included when fuzzing
        self._preprocessing_requests = []
        self._postprocessing_requests = []

    def __iter__(self):
        """ Iterate over FuzzingRequests """
        return iter(self._requests)

    def __deepcopy__(self, memo):
        """ Don't deepcopy this object, just return its reference"""
        return self

    def __contains__(self, request):
        """ Returns whether or not a request exists in the request list """
        return request in self._requests

    def add_request(self, request):
        """ Adds a new request to the collection of requests to be fuzzed """
        if request not in self._requests:
            self._requests.append(request)

    def exclude_preprocessing_request(self, request):
        """ Removes a request from the collection of requests to be fuzzed
            and adds that request to the preprocessing requests set

            @param request: The preprocessing request
            @type  request: Request

            @return: None
            @rtype : None

        """
        if request in self._requests:
            self._requests.remove(request)
        if request not in self._preprocessing_requests:
            self._preprocessing_requests.append(request)

    def exclude_postprocessing_request(self, request):
        """ Removes a request from the collection of requests to be fuzzed
            and adds that request to the postprocessing requests set

            @param request: The postprocessing request
            @type  request: Request

            @return: None
            @rtype : None

        """
        if request in self._requests:
            self._requests.remove(request)
        if request not in self._postprocessing_requests:
            self._postprocessing_requests.append(request)

    def set_all_requests(self, requests):
        """ Sets all requests in the request list """
        self._requests = list(requests)

    @property
    def all_requests(self):
        """ Returns the list of all requests that were defined in this
        request collection. This included the current request list and
        the excluded requests

        @return: The list of requests
        @rtype : List[Request]

        """
        return list(self._preprocessing_requests) + list(self._requests) + list(self._postprocessing_requests)

    @property
    def preprocessing_requests(self):
        """ Returns the list of the requests handled during preprocessing

        @return: The list of preprocessing requests
        @rtype : List[Request]

        """
        return list(self._preprocessing_requests)

    @property
    def postprocessing_requests(self):
        """ Returns the list of the requests handled during postprocessing

        @return: The list of postprocessing requests
        @rtype : List[Request]

        """
        return list(self._postprocessing_requests)

    @property
    def requests(self):
        """ Returns the list of requests being fuzzed

        @return: The list of requests being fuzzed
        @rtype : List[Request]

        """
        return list(self._requests)

    @property
    def size(self):
        """ Returns the number of requests being fuzzed

        @return: The number of request in collection.
        @rtype : Int

        """
        return len(self._requests)

    @property
    def size_all_requests(self):
        """ Returns the number of requests being fuzzed plus the number
        of requests used for pre and post-processing stages

        @return: The total number of requests
        @rtype : Int

        """
        return self.size + len(self._preprocessing_requests) + len(self._postprocessing_requests)
