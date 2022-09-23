# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" A checker that mutates tokens and reports bugs according to the specified criteria. """
from __future__ import print_function
from checkers.checker_base import *

import json
import sys

from engine.bug_bucketing import BugBuckets
import engine.core.sequences as sequences
import engine.primitives as primitives
from engine.errors import TimeOutException
from engine.core.requests import GrammarRequestCollection

class AuthTokenChecker(CheckerBase):
    """ If an authentication token is present, executes a set of checks according to the
    specified setting, such as removing or mutating the token with a user-specified dictionary """
    # Dictionary used for determining whether a request has already
    # been sent for the current generation.
    # { generation : set(request.hex_definitions) }
    generation_executed_requests = dict()

    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

        self._test_missing_token = None
        self._invalid_tokens = None

    def init_invalid_tokens(self):
        # Initialize the set of invalid tokens from the specified settings
        invalid_tokens_file_path = Settings().get_checker_arg(self._friendly_name, 'token_dict')
        try:
            if invalid_tokens_file_path is None:
                self._invalid_tokens = []
            else:
                self._invalid_tokens = json.load(open(invalid_tokens_file_path, encoding='utf-8'))

            for idx in range(0, len(self._invalid_tokens)):
                self._invalid_tokens[idx]["hash"] = request_utilities.str_to_hex_def(self._invalid_tokens[idx]["TokenName"])

        except Exception as error:
            print(f"Cannot import invalid tokens for checker: {error!s}")
            sys.exit(-1)

    def apply(self, rendered_sequence, lock):
        """ Substitute invalid tokens as specified in the settings for this checker.

        @param rendered_sequence: Object containing the rendered sequence information
        @type  rendered_sequence: RenderedSequence
        @param lock: Lock object used to sync more than one fuzzing job
        @type  lock: thread.Lock

        @return: None
        @rtype : None

        """
        if not rendered_sequence.sequence:
            return

        # Exit if time budget exceeded
        if Monitor().remaining_time_budget <= 0:
            raise TimeOutException('Exceed Timeout')

        if self._test_missing_token is None:
            self._test_missing_token = Settings().get_checker_arg(self._friendly_name, 'test_missing_token')
            if self._test_missing_token is None:
                self._test_missing_token = True
            self._missing_token_hash = request_utilities.str_to_hex_def("missing token")

        if self._invalid_tokens is None:
            self.init_invalid_tokens()

        # This needs to be set for the base implementation that executes the sequence.
        self._sequence = rendered_sequence.sequence

        last_request = self._sequence.last_request
        generation = self._sequence.length

        # Just run this checker once for the endpoint and method
        request_hash = last_request.method_endpoint_hex_definition
        if AuthTokenChecker.generation_executed_requests.get(generation) is None:
            # This is the first time this checker has seen this generation, create empty set of requests
            AuthTokenChecker.generation_executed_requests[generation] = set()
        elif request_hash in AuthTokenChecker.generation_executed_requests[generation]:
            # This request type has already been tested for this generation
            return
        # Add the last request to the generation_executed_requests dictionary for this generation
        AuthTokenChecker.generation_executed_requests[generation].add(request_hash)

        # Check whether this request contains an auth token and whether the token refresh command is specified.
        # If not, the checker is not applicable.
        def is_auth_token(req_block):
            req_primitive_type = req_block[0]
            return req_primitive_type == primitives.REFRESHABLE_AUTHENTICATION_TOKEN

        auth_token_blocks = list(map(lambda x: is_auth_token(x), last_request.definition))
        try:
            auth_token_idx = auth_token_blocks.index(True)
        except ValueError:
            return

        token_dict = GrammarRequestCollection().candidate_values_pool.get_candidate_values(
            primitives.REFRESHABLE_AUTHENTICATION_TOKEN
        )
        if not token_dict:
            self._checker_log.checker_print("No auth token found.")
            return

        self._checker_log.checker_print(f"Testing request: {last_request.endpoint} {last_request.method}")

        req_async_wait = Settings().get_max_async_resource_creation_time(last_request.request_id)
        new_seq = self._execute_start_of_sequence()
        # Add the last request of the sequence to the new sequence
        checked_seq = new_seq + sequences.Sequence(last_request)
        # Add the sent prefix requests for replay
        checked_seq.set_sent_requests_for_replay(new_seq.sent_request_data_list)
        # Create a placeholder sent data, so it can be replaced below when bugs are detected for replays
        checked_seq.append_data_to_sent_list("GET /", None,  HttpResponse(), max_async_wait_time=req_async_wait)

        # Render the current request combination, but get the list of primitive
        # values before they are concatenated.
        rendered_values, parser, tracked_parameters = \
            next(last_request.render_iter(self._req_collection.candidate_values_pool,
                                           skip=last_request._current_combination_id - 1,
                                           preprocessing=False,
                                           value_list=True))
        # Resolve dependencies
        if not Settings().ignore_dependencies:
            rendered_values = checked_seq.resolve_dependencies(rendered_values)

        # Run the specified token tests
        def send_data_and_report_bug(rendered_data, token_name, token_hash):
            response = request_utilities.send_request_data(rendered_data)
            responses_to_parse, resource_error, _ = async_request_utilities.try_async_poll(
                rendered_data, response, req_async_wait)
            parser_exception_occurred = False
            # Response may not exist if there was an error sending the request or a timeout
            if parser and responses_to_parse:
                # The response parser must be invoked so that dynamic objects created by this
                # request are initialized, adding them to the list of objects for the GC to clean up.
                parser_exception_occurred = not request_utilities.call_response_parser(parser, None,
                                                                                       request=last_request,
                                                                                       responses=responses_to_parse)
            if response and self._rule_violation(checked_seq, response, valid_response_is_violation=True):
                checked_seq.replace_last_sent_request_data(rendered_data, parser, response,
                                                           max_async_wait_time=req_async_wait)
                self._print_suspect_sequence(checked_seq, response)
                # The bucket origin must include the specific token scenario.
                # Otherwise, only the first type of token will be logged and the others
                # will be considered duplicates.
                bucket_type=f"{self.__class__.__name__}_{token_hash[:10]}"
                BugBuckets.Instance().update_bug_buckets(checked_seq, response.status_code,
                                                         origin=bucket_type,
                                                         additional_log_str=f"Token name: {token_name}")

        if self._test_missing_token:
            rendered_values[auth_token_idx] = ""
            request_payload = "".join(rendered_values)
            self._checker_log.checker_print(f"+++payload: {request_payload}.+++")
            send_data_and_report_bug(request_payload, "missing token", self._missing_token_hash)

        for invalid_token_json in self._invalid_tokens:
            # TODO: clean up and document format
            token_data = invalid_token_json["AccessToken"]
            token_name = invalid_token_json["TokenName"]
            token_hash = invalid_token_json["hash"]
            # TODO: generalize token prefix / add as setting
            if not token_data.startswith("Authorization"):
                token_data = f"Authorization: Bearer {token_data}"

            rendered_values[auth_token_idx] = token_data + "\r\n"
            request_payload = "".join(rendered_values)
            self._checker_log.checker_print(f"+++payload: {request_payload}.+++")
            send_data_and_report_bug(request_payload, token_name, token_hash)

        self._checker_log.checker_print(f"Tested request"
                                        f"{last_request.endpoint} {last_request.method}, combination "
                                        f"{last_request._current_combination_id}.")

    def _rule_violation(self, seq, response, valid_response_is_violation=True):
        """ Helper to check whether rule is violated.

        @param seq: The sequence whose last request we will try to render.
        @type  seq: Sequence Class object.
        @param response: Body of response.
        @type  response: Str.
        @param valid_response_is_violation: If set to True, a 20x status code
                in the response is treated as a violation
        @type  valid_response_is_violation: Bool

        @return: Whether rule is violated or not.
        @rtype : Bool

        """
        if response.status_code is None:
            # There is no response code in case of a connection error
            return False
        # This is the default general rule for this checker.
        # If a 500 (server error) is returned then it is an obvious bug.
        # If a 20x is returned, it is an authorization bug since tokens are expected to be invalid
        # Only allow the following invalid status codes to be returned (TODO: make this a checker option)
        valid_auth_error_codes = [401, 403]
        if response and (response.has_bug_code()\
        or (valid_response_is_violation and response.has_valid_code()))\
        or (response.status_code not in valid_auth_error_codes):
            return not self._false_alarm(seq, response)

        # If we reach this point no violation has occured.
        return False
