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
import typing

from engine.bug_bucketing import BugBuckets
import engine.core.sequences as sequences
import engine.core.requests as requests
from engine.core.requests import Request
import engine.primitives as primitives
from engine.primitives import CandidateValuesPool
from engine.errors import TimeOutException
from engine.errors import InvalidDictionaryException
from engine.core.requests import FailureInformation
import engine.dependencies as dependencies


def get_test_values(max_values: int, req: Request, static_dict=None,
                    value_gen_file_path=None,
                    override_value_generators=None,
                    random_seed=None):
    """First, test the dictionary values.
       If there are remaining iterations in the budget, get the
       remaining ones from the value generator.

       The Request contains just one block, which contains the primitive to be fuzzed.
       """
    count = 0
    static_values = []
    value_generator = None

    if static_dict is None and value_gen_file_path is None:
        raise Exception("Error: either a static dictionary or a value generator must be configured.")

    if static_dict is not None:
        static_pool = CandidateValuesPool()
        per_endpoint_user_dict = {}
        static_pool.set_candidate_values(static_dict, per_endpoint_user_dict)
        static_pool._add_examples = False
        static_pool._add_default_value = False
        try:
            static_values, _, _ = req.init_fuzzable_values(req.definition,
                                                           static_pool,
                                                           log_dict_err_to_main=False)
        except InvalidDictionaryException:
            pass
    if value_gen_file_path is not None:
        vg_pool = CandidateValuesPool()
        # todo: relative path
        vg_pool.set_value_generators(value_gen_file_path, random_seed=random_seed)

        if override_value_generators:
            vg_pool._value_generators = {
                k: override_value_generators.get(k, v) for k, v in vg_pool._value_generators.items()
            }
        vg_pool._add_examples = False
        vg_pool._add_default_value = False

        try:
            vgen_fuzzable_values, _, _ = req.init_fuzzable_values(req.definition,
                                                                  vg_pool,
                                                                  log_dict_err_to_main=False)
        except InvalidDictionaryException:
            request_block = req.definition[0]
            primitive_type = request_block[0]
            # If this primitive type does not appear in the invalid dictionary or user-specified value generators,
            # fuzz it with the generic string generator.
            if primitive_type == primitives.FUZZABLE_GROUP:
                quoted = request_block[3]
                examples = request_block[4]
            elif primitive_type in [primitives.CUSTOM_PAYLOAD,
                                    primitives.CUSTOM_PAYLOAD_HEADER,
                                    primitives.CUSTOM_PAYLOAD_QUERY,
                                    primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX]:
                quoted = request_block[2]
                examples = request_block[3]
            else:
                quoted = request_block[2]
                examples = request_block[3]

            fuzzable_string = primitives.restler_fuzzable_string("fuzzstring", quoted=quoted, examples=examples)
            vgen_fuzzable_values, _, _ = req.init_fuzzable_values([fuzzable_string],
                                                                  vg_pool,
                                                                  log_dict_err_to_main=False)

        # The fuzzable values should always be a list of length 1,
        # because only one request block is being fuzzed at a time
        if len(vgen_fuzzable_values) != 1:
            raise Exception(f"There should only be one item in fuzzable values, {len(vgen_fuzzable_values)} found.")

        # Initialize the value generator.
        value_gen_tracker = {}  # not used
        fuzzable_request_blocks = [0]  # Just one request block being fuzzed
        value_generators = requests.Request.init_value_generators(fuzzable_request_blocks, vgen_fuzzable_values,
                                                                  value_gen_tracker)
        if len(value_generators) == 1:  # Generator for the one request block
            value_generator = value_generators[0]

    primitive_block_index = 0  # currently, only one primitive block at a time is supported
    num_static_values = 0
    if len(static_values) > 0:
        static_values = static_values[primitive_block_index]
        num_static_values = len(static_values)

    while count < max_values:
        if count < num_static_values:
            next_value = static_values[count]
            if not isinstance(next_value, str):
                next_values = request_utilities.resolve_dynamic_primitives([next_value], vg_pool)
                next_value = next_values[0]
            yield next_value
        elif value_generator is not None:
            rendered_values = [value_generator]
            rendered_values = request_utilities.resolve_dynamic_primitives(rendered_values, vg_pool)
            yield rendered_values[primitive_block_index]
        count += 1


class InvalidValueChecker(CheckerBase):
    """ Checker for fuzzing API parameters with invalid values. """
    # Dictionary used for determining whether a request has already
    # been sent for the current generation.
    # { generation : set(request.hex_definitions) }
    generation_executed_requests = dict()

    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)
        # Fuzzing settings
        self._fuzz_valid = True
        self._fuzz_invalid = True

        # The custom invalid mutations dictionary
        self._custom_invalid_mutations = None

        # The invalid dictionary mutations pool
        self._invalid_static_candidate_values_pool: CandidateValuesPool = None

        # The pool with dynamic generators
        self._invalid_generated_candidate_values_pool: CandidateValuesPool = None

        # The total number of invalid combinations to test
        self._max_invalid_combinations: int = None

        # The file path of the default value generators included with the checker
        self._value_generators_file_path = None

        # The random seed override
        self._override_random_seed = None

    def init_mutations(self):
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        default_value_generators_file_path = os.path.join(current_file_dir, "invalid_value_checker_value_gen.py")

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

        self._value_generators_file_path = Settings().get_checker_arg(self._friendly_name, 'custom_value_generators')
        if self._value_generators_file_path is None:
            self._value_generators_file_path = default_value_generators_file_path

        self._override_random_seed = Settings().get_checker_arg(self._friendly_name, 'random_seed')
        if self._override_random_seed is None:
            self._override_random_seed = Settings().random_seed

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
        if rendered_sequence.sequence is None or\
        rendered_sequence.failure_info == FailureInformation.SEQUENCE or\
        (rendered_sequence.valid and not self._fuzz_valid) or\
        (not rendered_sequence.valid and not self._fuzz_invalid):
            return

        if not self._custom_invalid_mutations:
            self.init_mutations()

        self._sequence = rendered_sequence.sequence
        last_request = self._sequence.last_request
        generation = self._sequence.length
        (last_rendered_schema_request,_) = self._sequence.last_request._last_rendered_schema_request
        self._checker_log.checker_print(f"Testing request: {last_request.endpoint} {last_request.method}")

        # Note: this hash should be the last rendered schema hex definition,
        # so each of the different schema variations of the request
        # are fuzzed separately (since they may contain different parameters).
        request_hash = last_rendered_schema_request.hex_definition
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
        def should_fuzz(req_block):
            """Fuzz every fuzzable or custom payload.
               - Dynamic objects (readers) appear in static strings, so they are not fuzzed.
                 These are handled separately in the invalid dynamic object checker.
            """
            req_primitive_type = req_block[0]
            return "_fuzzable_" in req_primitive_type or "_custom_" in req_primitive_type

        fuzzable_parameter_value_blocks = list(map(lambda x : should_fuzz(x), last_rendered_schema_request.definition))
        num_fuzzable_blocks = len(list(filter(lambda x: x, fuzzable_parameter_value_blocks)))
        if num_fuzzable_blocks == 0:
            return

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
        rendered_values, parser, tracked_parameters, updated_writer_variables = \
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

        self._checker_log.checker_print(f"Budget: {param_budget} values per parameter.")

        for idx, is_fuzzable in enumerate(fuzzable_parameter_value_blocks):
            if not is_fuzzable:
                continue

            # Save the original request block.
            request_block = last_rendered_schema_request.definition[idx]
            primitive_type = request_block[0]

            # Create a request with this block being the only part of its definition, and get the
            # fuzzable values.
            temp_req = requests.Request([request_block])

            # TODO: add the parameter name to value generators so it can be obtained here.
            if primitive_type == primitives.FUZZABLE_GROUP:
                field_name = request_block[1]

            elif primitive_type in [primitives.CUSTOM_PAYLOAD,
                                    primitives.CUSTOM_PAYLOAD_HEADER,
                                    primitives.CUSTOM_PAYLOAD_QUERY,
                                    primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX]:
                field_name = request_block[1]
            else:
                field_name = request_block[4]

            logged_param = "" if field_name is None else f", name: {field_name}"
            self._checker_log.checker_print(f"Fuzzing request block {idx}, type: {primitive_type}{logged_param}")

            tv = get_test_values(param_budget, temp_req, self._custom_invalid_mutations,
                                 self._value_generators_file_path,
                                 random_seed=self._override_random_seed)

            # Now plug in the test value into the rendered values, saving the original rendering
            orig_rendered_values = rendered_values[idx]
            try:
                # Only one value is being fuzzed at a time
                for fuzzed_value in tv:
                    rendered_values[idx] = fuzzed_value
                    if not isinstance(fuzzed_value, str):
                        print("not a string!")
                    rendered_data = "".join(rendered_values)

                    # Check time budget
                    if Monitor().remaining_time_budget <= 0:
                        raise TimeOutException('Exceed Timeout')

                    fuzzed_combinations += 1
                    response = request_utilities.send_request_data(rendered_data)
                    if response.has_valid_code():
                        fuzzed_writer_variables = Request.get_writer_variables(temp_req.definition)
                        for name,v in updated_writer_variables.items():
                            # If the writer variable is being fuzzed, the fuzzed value must be
                            # specified.
                            if fuzzed_writer_variables and fuzzed_writer_variables[0] == name:
                                v = fuzzed_value
                            dependencies.set_variable(name, v)

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
                    status_code = response.status_code

                    if response and self._rule_violation(checked_seq, response, valid_response_is_violation=False):
                        checked_seq.replace_last_sent_request_data(rendered_data, parser, response, max_async_wait_time=req_async_wait)
                        self._print_suspect_sequence(checked_seq, response)
                        BugBuckets.Instance().update_bug_buckets(checked_seq, response.status_code, origin=self.__class__.__name__)

            finally:
                rendered_values[idx] = orig_rendered_values

        self._checker_log.checker_print(f"Tested {fuzzed_combinations} combinations for request "
                                        f"{last_request.endpoint} {last_request.method}, combination "
                                        f"{last_request._current_combination_id}")
