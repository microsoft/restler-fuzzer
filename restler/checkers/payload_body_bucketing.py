# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Handles bucketizing payload body checker bugs """
import os
import utils.logger as logger
import engine.fuzzing_parameters.fuzzing_utils as utils
from engine.transport_layer.messaging import DELIM

INVALID_JSON_STR = 'InvalidJson'

class PayloadBodyBuckets():
    def __init__(self):
        """ Initializes PayloadBodyBuckets class """
        self._buckets = dict() # {Request, set(error_strs)}

    def add_bug(self, request, new_request_data):
        """ Adds a bug to the payload body buckets log if it is unique.

        @param request: The request being fuzzed
        @type  request: Request
        @param new_request_data: The request data of the new request that
                                 includes the fuzzed payload body.
        @type  new_request_data: Str

        @return: Tuple containing the error string and the response body
        @rtype : Tuple(str, str) or None

        """
        # Extract the body from the new request data
        new_body = utils.get_response_body(new_request_data)
        with open(os.path.join(logger.LOGS_DIR, 'payload_buckets.txt'), 'a') as file:
            # Check to see if we have logged any bugs for this request yet
            if request.method_endpoint_hex_definition not in self._buckets:
                self._buckets[request.method_endpoint_hex_definition] = set()
                # Write the header for this particular request to the log
                file.write(f'{request.method} {request.endpoint_no_dynamic_objects}\n')

            error_str = self._get_error_str(request, new_body) or 'Other'
            if error_str not in self._buckets[request.method_endpoint_hex_definition]:
                if error_str == INVALID_JSON_STR:
                    # body is invalid JSON, so just extract what's at the end of the
                    # request for logging purposes
                    new_body = new_request_data.split(DELIM)[-1]
                self._buckets[request.method_endpoint_hex_definition].add(error_str)
                file.write(f'\t{error_str}\n\t{new_body}\n\n')
                return (error_str, new_body)
        return None

    def _get_error_str(self, request, new_body):
        """ Gets the error string associated with this bug

        @param request: The request being fuzzed
        @type  request: Request
        @param new_body: The fuzzed body of the request to compare
        @type  new_body: Str

        @return: The error string or None
        @rtype : Str or None

        """
        if new_body:
            # Compare the new body to the original request for a type mismatch
            mismatch = request.body_schema.has_type_mismatch(new_body)
            if mismatch:
                return f'TypeMismatch_{mismatch}'
            # Compare the new body to the original request for a missing struct
            missing = request.body_schema.has_struct_missing(new_body)
            if missing:
                return f'StructMissing_{missing}'
        else:
            return INVALID_JSON_STR

        return None
