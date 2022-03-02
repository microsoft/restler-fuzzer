# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Implements logic for the user-directed invalid value checker. """
from __future__ import print_function

from checkers.checker_base import *
import time
import uuid
import json
import sys
import os

from engine.bug_bucketing import BugBuckets
import engine.dependencies as dependencies
import engine.core.sequences as sequences
import engine.core.requests as requests
import engine.primitives as primitives

from engine.errors import TimeOutException
from engine.errors import InvalidDictionaryException

from utils.logger import raw_network_logging as RAW_LOGGING


class InvalidValueChecker(CheckerBase):
    """ Checker for fuzzing API parameters with invalid values. """
    # Dictionary used for determining whether or not a request has already
    # been sent for the current generation.
    # { generation : set(request.hex_definitions) }
    generation_executed_requests = dict()

    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

        self._custom_invalid_mutations = None

    def init_mutations(self):
        current_file_dir = os.path.dirname(os.path.abspath(__file__))

        invalid_mutations_file_path = Settings().get_checker_arg(self._friendly_name, 'custom_dictionary')

        try:
            if invalid_mutations_file_path is None:
                self._custom_invalid_mutations = {}
            else:
                self._custom_invalid_mutations = json.load(open(invalid_mutations_file_path, encoding='utf-8'))

        except Exception as error:
            print(f"Cannot import invalid mutations dictionary for checker: {error!s}")
            sys.exit(-1)

        self._max_invalid_combinations = Settings().get_checker_arg(self._friendly_name, 'max_combinations')

        value_generators_file_path = Settings().get_checker_arg(self._friendly_name, 'custom_value_generators')
        if value_generators_file_path is None:
            value_generators_file_path = os.path.join(current_file_dir, "invalid_value_checker_value_gen.py")

        self._invalid_candidate_values_pool =  primitives.CandidateValuesPool()
        per_endpoint_invalid_custom_mutations = {} # Per-endpoint mutations are not supported yet
        self._invalid_candidate_values_pool.set_candidate_values(self._custom_invalid_mutations,
                                                                 per_endpoint_invalid_custom_mutations)
        self._invalid_candidate_values_pool.set_value_generators(value_generators_file_path)
        self._invalid_candidate_values_pool._add_examples = False
        self._invalid_candidate_values_pool._add_default_value = False

    def apply(self, rendered_sequence, lock):
        """ Fuzzes each value in the parameters of this request as specified by
        the custom dictionary and settings for this checker.

        @param rendered_sequence: Object containing the rendered sequence information
        @type  rendered_sequence: RenderedSequence
        @param lock: Lock object used to sync more than one fuzzing job
        @type  lock: thread.Lock

        @return: None
        @rtype : None

        """
        # If this is not a valid sequence, do not attempt to fuzz the parameters.
        #if not rendered_sequence.valid:
        #    return

        if not rendered_sequence.sequence:
            return

        if not self._custom_invalid_mutations:
            self.init_mutations()

        self._sequence = rendered_sequence.sequence
        last_request = self._sequence.last_request

        generation = self._sequence.length

        # Note: this hash must be the hex definition, so each of the different schema variations of the request
        # are fuzzed separately (since they may contain different parameters).
        request_hash = last_request.hex_definition
        if InvalidValueChecker.generation_executed_requests.get(generation) is None:
            # This is the first time this checker has seen this generation, create empty set of requests
            InvalidValueChecker.generation_executed_requests[generation] = set()
        elif request_hash in InvalidValueChecker.generation_executed_requests[generation]:
            # This request type has already been tested for this generation
            return
        # Add the last request to the generation_executed_requests dictionary for this generation
        InvalidValueChecker.generation_executed_requests[generation].add(request_hash)

        # Get a list of all the fuzzable parameters in this request.
        # The following list will contain a boolean value indicating whether the
        # corresponding request block is a parameter value that can be fuzzed.
        def should_fuzz(request_block):
            """Fuzz every fuzzable or custom payload.
               - Dynamic objects (readers) appear in static strings, so they are not fuzzed.
                 These are handled separately in the invalid dynamic object checker.
            """
            primitive_type = request_block[0]
            return "_fuzzable_" in primitive_type or "_custom_" in primitive_type
        fuzzable_parameter_value_blocks = list(map(lambda x : should_fuzz(x), last_request.definition))
        num_fuzzable_blocks = len(list(filter(lambda x: x, fuzzable_parameter_value_blocks)))
        if num_fuzzable_blocks == 0:
            return

        req_async_wait = Settings().get_max_async_resource_creation_time(last_request.request_id)
        new_seq = self._execute_start_of_sequence()
        # Add the last request of the sequence to the new sequence
        checked_seq = new_seq + sequences.Sequence(last_request)
        # Add the sent prefix requests for replay
        checked_seq.set_sent_requests_for_replay(new_seq.sent_request_data_list)
        # Create a placeholder sent data so it can be replaced below when bugs are detected for replays
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

        # For each fuzzable primitive, plug in all the values from the invalid dictionary or
        # dynamic value generators.
        self._checker_log.checker_print(f"Found {num_fuzzable_blocks} fuzzable blocks.")

        fuzzed_combinations = 0
        if self._max_invalid_combinations is None:
            param_budget = 100
        else:
            param_budget = max(1, self._max_invalid_combinations / num_fuzzable_blocks)
        for idx, is_fuzzable in enumerate(fuzzable_parameter_value_blocks):
            if not is_fuzzable:
                continue

            # Save the original request block.
            request_block = last_request.definition[idx]
            primitive_type = request_block[0]

            # Create a request with this block being the only part of its definition, and get the
            # fuzzable values.
            temp_req = requests.Request([request_block])

            # TODO: add the parameter name to value generators so it can be obtained here.
            if primitive_type == primitives.FUZZABLE_GROUP:
                field_name = request_block[1]

            elif primitive_type in [ primitives.CUSTOM_PAYLOAD,
                                        primitives.CUSTOM_PAYLOAD_HEADER,
                                        primitives.CUSTOM_PAYLOAD_QUERY,
                                        primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX ]:
                field_name = request_block[1]
            else:
                field_name = request_block[4]
            self._checker_log.checker_print(f"Fuzzing parameter {field_name}")


            try:
                fuzzable_values, _, _ = temp_req.init_fuzzable_values(temp_req.definition, self._invalid_candidate_values_pool)
            except InvalidDictionaryException:
                # If this primitive type does not appear in the invalid dictionary or value generators,
                # fuzz it with the generic value generator.
                if primitive_type == primitives.FUZZABLE_GROUP:
                    quoted = request_block[3]
                    examples = request_block[4]
                elif primitive_type in [ primitives.CUSTOM_PAYLOAD,
                                         primitives.CUSTOM_PAYLOAD_HEADER,
                                         primitives.CUSTOM_PAYLOAD_QUERY,
                                         primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX ]:
                    quoted = request_block[2]
                    examples = request_block[3]
                else:
                    quoted = request_block[2]
                    examples = request_block[3]

                fuzzable_string = primitives.restler_fuzzable_string("fuzzstring", is_quoted=quoted, examples=examples)
                fuzzable_values, _, _ = temp_req.init_fuzzable_values([fuzzable_string], self._invalid_candidate_values_pool)

            # The fuzzable values should always be a list of length 1, because only one request block is being fuzzed at a time
            if len(fuzzable_values) != 1:
                raise Exception(f"There should only be one item in fuzzable values, {len(fuzzable_values)} found.")

            value_gen_tracker={} # not used
            fuzzable_request_blocks = [0] # Just one current request block being fuzzed
            value_generators = requests.Request.init_value_generators(fuzzable_request_blocks, fuzzable_values,
                                                                      value_gen_tracker)

            if value_generators:
                # Each element of fuzzable values must be a list
                fuzzable_values[0] = [value_generators[0]]
                using_value_generator = True
            else:
                using_value_generator = False

            # Now plug in this list into the rendered values, saving the original rendering
            orig_rendered_values=rendered_values[idx]
            try:
                count = 0
                while count < param_budget:
                    # Since only one value is being fuzzed at a time, simply choose between the list of values
                    # and value generator from the first item in the list.
                    if using_value_generator:
                        fuzzed_value = fuzzable_values[0][0]
                    else:
                        if count >= len(fuzzable_values[0]):
                            break
                        fuzzed_value = fuzzable_values[0][count]

                    rendered_values[idx] = fuzzed_value

                    rendered_values = request_utilities.resolve_dynamic_primitives(rendered_values, self._invalid_candidate_values_pool)
                    rendered_data = "".join(rendered_values)

                    # Check time budget
                    if Monitor().remaining_time_budget <= 0:
                        raise TimeOutException('Exceed Timeout')

                    count += 1
                    fuzzed_combinations += 1

                    response = request_utilities.send_request_data(rendered_data)
                    responses_to_parse, resource_error, _ = async_request_utilities.try_async_poll(
                        rendered_data, response, req_async_wait)
                    parser_exception_occurred = False
                    # Response may not exist if there was an error sending the request or a timeout
                    if parser and responses_to_parse:
                        # The response parser must be invoked so that dynamic objects created by this
                        # request are initialized, adding them to the list of objects for the GC to clean up.
                        parser_exception_occurred = not request_utilities.call_response_parser(parser, None, request=last_request, responses=responses_to_parse)
                    status_code = response.status_code

                    if response and self._rule_violation(checked_seq, response, valid_response_is_violation=False):
                        checked_seq.replace_last_sent_request_data(rendered_data, parser, response, max_async_wait_time=req_async_wait)
                        self._print_suspect_sequence(checked_seq, response)
                        BugBuckets.Instance().update_bug_buckets(checked_seq, response.status_code, origin=self.__class__.__name__)

            finally:
                rendered_values[idx] = orig_rendered_values

        self._checker_log.checker_print(f"Tested {fuzzed_combinations} combinations for request {last_request.endpoint} {last_request.method}, combination {last_request._current_combination_id}")
