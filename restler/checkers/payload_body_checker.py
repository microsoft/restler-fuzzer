# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Implements logic for payload body fuzzing checker. """
from __future__ import print_function

from checkers.checker_base import *

import os
import os.path
import copy
import json
import random
import re

from copy import copy

from engine.bug_bucketing import BugBuckets
import engine.dependencies as dependencies
import engine.core.requests as requests
import engine.core.sequences as sequences
from engine.core.fuzzing_monitor import Monitor
from engine.core.request_utilities import str_to_hex_def
from engine.errors import TimeOutException
import engine.primitives as primitives
from engine.fuzzing_parameters.body_schema import BodySchema

from utils.logger import raw_network_logging as RAW_LOGGING

from checkers.body_schema_fuzzer import *
from checkers.response_analyzer import ResponseTracker
from checkers.payload_body_bucketing import *
from engine.fuzzing_parameters.fuzzing_utils import *

class PayloadBodyChecker(CheckerBase):
    """ Checker for payload body fuzzing. """

    def __init__(self, req_collection, fuzzing_requests):
        CheckerBase.__init__(self, req_collection, fuzzing_requests)

        # alias the log
        self._log = self._checker_log.checker_print

        # initialize
        self._examples_values = {}
        self._response_values = {}
        self._keywords_for_response = self._get_custom_payload_uuid4_suffix()

        # init fuzz task tracking
        self._pipelines = []
        self._trackers = {}
        self._global_count = 0
        self._global_bound = -1
        self._refresh_per_task = True
        self._refresh_req = False
        self._acc_response = True
        self._greedy_response = True
        self._keyword_response = True
        self._fixed_budget_max_combination = 1000
        self._fixed_budget_pipeline_width = 100
        self._fuzz_valid = True
        self._fuzz_invalid = True
        self._start_with_examples = True
        self._size_dep_budget = True
        self._setup_done = False
        self._use_feedback = True
        self._current_task_tag = ''
        self._fuzzed_requests = set()
        self._buckets = PayloadBodyBuckets()

        def set_var(member_var, arg):
            """ helper for setting member variables from settings """
            val = Settings().get_checker_arg(self.friendly_name, arg)
            if val is not None:
                return val
            return member_var
        # 'start_with_valid' setting was kept for backwards compatibility.
        # This setting behaves identically to 'fuzz_valid'. 'fuzz_valid' takes priority.
        self._fuzz_valid = set_var(self._fuzz_valid, 'start_with_valid')
        self._fuzz_valid = set_var(self._fuzz_valid, 'fuzz_valid')
        self._fuzz_invalid = set_var(self._fuzz_invalid, 'fuzz_invalid')
        self._start_with_examples = set_var(self._start_with_examples, 'start_with_examples')
        self._size_dep_budget = set_var(self._size_dep_budget, 'size_dep_budget')
        self._use_feedback = set_var(self._use_feedback, 'use_feedback')
        self._fixed_budget_max_combination = set_var(self._fixed_budget_max_combination, 'fixed_budget_max_combination')
        self._fixed_budget_pipeline_width = set_var(self._fixed_budget_pipeline_width, 'fixed_budget_pipeline_width')
        self._recipe_file = Settings().get_checker_arg(
            self.friendly_name, 'recipe_file'
        )

    def apply(self, rendered_sequence, lock):
        """ Applies check for fuzzing request payload body

        @param rendered_sequence: Object containing the rendered sequence information
        @type  rendered_sequence: RenderedSequence
        @param lock: Lock object used to sync more than one fuzzing job
        @type  lock: thread.Lock

        @return: None
        @type  : None

        """
        # one-time setup
        if not self._setup_done:
            # read the customized fuzzing recipe, if provided
            if self._recipe_file:
                with open(self._recipe_file, 'r') as fr:
                    recipe_str = fr.read()
                    recipe_json = json.loads(recipe_str)
                    self._setup_fuzzing_pipelines(recipe_json)

            # log
            self._log(f'fuzzing valid {self._fuzz_valid}')
            self._log(f'fuzzing invalid {self._fuzz_invalid}')
            self._log(f'start with examples {self._start_with_examples}')
            self._log(f'size dep budget {self._size_dep_budget}')
            self._log(f'use feedback {self._use_feedback}')
            self._log(f'recipe {self._recipe_file}')

            # finish one-time setup
            self._setup_done = True

        if not rendered_sequence.sequence or\
        (rendered_sequence.valid and not self._fuzz_valid) or\
        (not rendered_sequence.valid and not self._fuzz_invalid):
            return

        self._sequence = rendered_sequence.sequence
        # only fuzz the body of the last request
        last_request = self._sequence.last_request

        # check if the request has non-empty body
        if not last_request.body_schema:
            return

        last_request_def = str_to_hex_def(last_request.method) + last_request.request_id
        # check if the request has been fuzzed
        if self._mode == 'normal' and last_request_def in self._fuzzed_requests:
            self._log(f'Skip visited request {last_request.endpoint_no_dynamic_objects}')
            return

        self._log(f'Start fuzzing request: {last_request.method} {last_request.endpoint_no_dynamic_objects}')
        self._fuzzed_requests.add(last_request_def)

        # record and log the body schema to be fuzzed
        node_num = last_request.body_schema.node_count
        self._log(f'#node: {node_num}')

        # reset the response value mapping and global budget
        self._response_values = {}
        self._global_count = 0

        # get the corresponding request examples
        self._examples_values = {}
        if last_request.examples:
            for example in last_request.examples.body_examples:
                tag_content = example.get_schema_tag_mapping()
                for tag in tag_content:
                    if tag in self._examples_values:
                        self._examples_values[tag].append(tag_content[tag])
                    else:
                        self._examples_values[tag] = [tag_content[tag]]

        # set the initial starting body schemas
        if last_request.examples and self._start_with_examples:
            body_schema_list = list(last_request.examples.body_examples) + [last_request.body_schema]
        else:
            body_schema_list = [last_request.body_schema]

        # trigger different fuzzing modes
        if self._pipelines:
            self._log('Fuzz using custom recipe')
            self._run_pipelines(last_request, body_schema_list)
        elif self._use_feedback:
            self._log('Fuzz using dynamic feedback')
            self._run_feedback_fuzzing(last_request, body_schema_list)
        else:
            self._log('Fuzz using static strategy')
            self._run_oneway_fuzzing(last_request, body_schema_list)

    def _setup_fuzzing_pipelines(self, recipe):
        """ Setup fuzzing pipelines based on the run-time config.

        @param recipe: Fuzzing recipe (run-time config.)
        @type  recipe: Dict

        @return: None
        @rtype:  None

        """
        if 'refresh_response' in recipe:
            self._refresh_per_task = recipe['refresh_response']
        if 'accumulate_response' in recipe:
            self._acc_response = recipe['accumulate_response']
        if 'greedy_response' in recipe:
            self._greedy_response = recipe['greedy_response']
        if 'keyword_response' in recipe:
            self._keyword_response = recipe['keyword_response']
        if 'global_bound' in recipe:
            self._global_bound = recipe['global_bound']
        # 'start_with_valid' kept for backwards compatibility
        if 'start_with_valid' in recipe:
            self._fuzz_valid = recipe['start_with_valid']
        if 'fuzz_valid' in recipe:
            self._fuzz_valid = recipe['fuzz_valid']
        if 'fuzz_invalid' in recipe:
            self._fuzz_invalid = recipe['fuzz_invalid']
        if 'start_with_examples' in recipe:
            self._start_with_examples = recipe['start_with_examples']
        if 'size_dep_budget' in recipe:
            self._size_dep_budget = recipe['size_dep_budget']

        recipe_fuzzer_mapping = {
            'structure_propagate_strategy': 'propagate_strategy',
            'structure_max_combination': 'max_combination',
            'structure_max_propagation': 'max_propagation',
            'structure_shuffle_combination': 'shuffle_combination',
            'structure_shuffle_propagate': 'shuffle_propagation',
            'random_seed': 'random_seed'
        }

        recipe_interp_mapping = {
            'value_search_strategy': 'fuzz_strategy',
            'value_max_combination': 'max_combination',
            'value_use_examples_for_default': 'use_examples_for_default',
            'value_use_response_for_default': 'use_response_for_default',
            'value_use_embedded_for_fuzzable': 'use_embedded_for_fuzzable',
            'value_use_wordbook_for_fuzzable': 'use_wordbook_for_fuzzable'
        }

        recipe_pipeline_mapping = {
            'pipeline_max_combination': 'max_combination',
            'pipeline_max_propagation': 'max_propagation',
            'pipeline_propagation_strategy': 'propagation_strategy',
            'pipeline_fair_propagation': 'fair_propagation',
            'random_seed': 'random_seed'
        }

        def overwrite_options(src_recipe, dst_config, mapping):
            for recipe_option in mapping:
                config_option = mapping[recipe_option]
                if recipe_option in src_recipe:
                    dst_config[config_option] = src_recipe[recipe_option]

        # checker default
        default_fuzzer = {}
        default_interp = {
            'get_wordbook_values': self._req_collection.candidate_values_pool.get_candidate_values,
            'get_examples_values': self._get_examples_values,
            'get_response_values': self._get_response_values
        }
        default_pipeline = {
            'max_combination': 50,
            'max_propagation': 10,
            'propagation_strategy': 'RD',
            'fair_propagation': False,
            'random_seed': 0
        }

        # user default
        if 'default' in recipe:
            user_default = recipe['default']

            overwrite_options(
                user_default, default_fuzzer, recipe_fuzzer_mapping
            )
            overwrite_options(
                user_default, default_interp, recipe_interp_mapping
            )
            overwrite_options(
                user_default, default_pipeline, recipe_pipeline_mapping
            )

        # setup pipelines
        if 'pipelines' in recipe:
            pipelines = recipe['pipelines']

            for unit in pipelines:
                # name
                if 'name' not in unit:
                    self._log('No name for pipeline')
                    continue
                name = unit['name']

                fuzzer_config = default_fuzzer.copy()
                overwrite_options(unit, fuzzer_config, recipe_fuzzer_mapping)

                interp_config = default_interp.copy()
                overwrite_options(unit, interp_config, recipe_interp_mapping)

                pipeline_config = default_pipeline.copy()
                overwrite_options(
                    unit, pipeline_config, recipe_pipeline_mapping)

                # rules
                if 'rules' in unit:
                    rules = unit['rules']
                    tasks = [
                        self._get_task(
                            rule, fuzzer_config, interp_config
                        ) for rule in rules
                    ]
                    self._add_pipeline(name, tasks, pipeline_config)

                else:
                    self._log(f'No rule specified in pipeline {name}')

    def _get_task(self, rule, fuzzer_config, interp_config):
        """ Return a fuzzing task

        @param rule: Task rule (structural fuzzing)
        @type  rule: String
        @param fuzzer_config: Fuzzer configuration
        @type  fuzzer_config: Dict
        @param interp_config: Interpreter configuration
        @type  interp_config: Dict

        @return: Fuzzing task
        @rtype:  FuzzTask

        """
        rule_fuzzer_mapping = {
            'SingleDrop': BodyFuzzer_Drop(self._log, 'single'),
            'SingleSelect': BodyFuzzer_Select(self._log, 'single'),
            'SingleType': BodyFuzzer_Type(self._log, 'single'),
            'SingleDuplicate': BodyFuzzer_Duplicate(self._log, 'single'),
            'PathDrop': BodyFuzzer_Drop(self._log, 'path'),
            'PathSelect': BodyFuzzer_Select(self._log, 'path'),
            'PathType': BodyFuzzer_Type(self._log, 'path'),
            'PathDuplicate': BodyFuzzer_Duplicate(self._log, 'path'),
            'AllDrop': BodyFuzzer_Drop(self._log, 'all'),
            'AllSelect': BodyFuzzer_Select(self._log, 'all'),
            'AllType': BodyFuzzer_Type(self._log, 'all'),
            'AllDuplicate': BodyFuzzer_Duplicate(self._log, 'all'),
            'TypeCheap': BodyFuzzer_Type_Cheap(self._log),
            'TypeInternal': BodyFuzzer_TypeInternal(self._log),
            'TypeLeaf': BodyFuzzer_TypeLeaf(self._log),
            'DuplicateObject': BodyFuzzer_Duplicate_Object(self._log),
            'DuplicateArray': BodyFuzzer_Duplicate_Array(self._log),
            'DROP': BodyFuzzer_Drop(self._log, 'path'),
            'SELECT': BodyFuzzer_Select(self._log, 'path'),
            'TYPE': BodyFuzzer_Type(self._log, 'single'),
            'DUPLICATE': BodyFuzzer_Duplicate_Object(self._log)
        }

        if rule in rule_fuzzer_mapping:
            fuzzer = rule_fuzzer_mapping[rule]
        else:
            self._log(f'ERROR: Unknown rule {rule}')
            return None

        return self.FuzzTask(fuzzer, fuzzer_config, interp_config)

    def _add_pipeline(self, name, tasks, pipeline_config):
        """ Add a pipeline to the record

        @param name: Pipeline name
        @type  name: String
        @param tasks: Pipeline tasks
        @type  tasks: List
        @param pipeline_config: Pipeline configuration
        @type  pipeline_config: Dict

        @return: None
        @rtype:  None

        """
        self._pipelines.append(
            {
                'name': name,
                'tasks': tasks,
                'config': pipeline_config
            }
        )

    def _run_pipelines(self, request, body_schema_list):
        """ Run all the pipeline tasks

        @param request: The request to fuzz
        @type  request: Request
        @param body_schema_list: A list of seed body schema
        @type  body_schema_list: List [BodySchema]

        @return: None
        @rtype:  None

        """
        # refresh once
        if not self._refresh_per_task:
            self._refresh(request)

        # ignore group: fuzzable string
        string_group = self._req_collection.candidate_values_pool.get_candidate_values(
            primitives.FUZZABLE_STRING
        )
        ignore = set(string_group)

        # set variable budget
        if self._size_dep_budget:
            node_num = body_schema_list[-1].node_count
            max_combination = max(200, 10 * node_num)
            max_propagation = max(20, node_num)

        for pipeline in self._pipelines:
            tag = pipeline['name']
            # setup tracker
            if tag in self._trackers:
                tracker = self._trackers[tag]

            else:
                tracker = ResponseTracker(ignore, False, self._log)
                self._trackers[tag] = tracker

            # refresh for each task
            if self._refresh_per_task:
                self._refresh(request)

            # execute pipeline
            pipe_tasks = pipeline['tasks']
            pipe_options = pipeline['config']

            strategy = pipe_options['propagation_strategy']
            if not self._size_dep_budget:
                max_combination = pipe_options['max_combination']
                max_propagation = pipe_options['max_propagation']
            fair_propagation = pipe_options['fair_propagation']

            schema_pool = body_schema_list

            for task_idx, task in enumerate(pipe_tasks):
                if fair_propagation:
                    ratio = 10 ** (len(pipe_tasks) - task_idx)
                    max_propagation = max(max_combination / ratio, 1)

                # generate all possible tests up to #max_propagation seeds
                schema_group_list = [
                    task.fuzzer.run(seed_schema, task.fuzzer_config)  # [1:]
                    for seed_schema in schema_pool[:max_propagation]
                ]

                if strategy == 'BF':
                    combination = itertools.zip_longest(*schema_group_list)
                    groups = [filter(None, list(tu)) for tu in combination]

                    acc_pool = []
                    for group in groups:
                        acc_pool += group

                else:  # DF and RD
                    acc_pool = []
                    for group in schema_group_list:
                        acc_pool += group

                    if strategy == 'RD':
                        random.Random(
                            pipe_options['random_seed']).shuffle(acc_pool)

                del schema_group_list

                schema_pool = []
                unique_signs = set([])
                for schema_test in acc_pool:
                    schema_sign = schema_test.get_signature()
                    if schema_sign not in unique_signs:
                        schema_pool.append(schema_test)
                        unique_signs.add(schema_sign)

                        if len(schema_pool) >= max_combination:
                            break

            self._log(f'Task begin {tag} (#: {len(schema_pool)})')
            self._current_task_tag = tag

            for schema in schema_pool:
                body_blocks_fuzzed = schema.fuzz_body_blocks(task.interp_config)

                # iterate
                for body_blocks in body_blocks_fuzzed:
                    self._exec_request_with_new_body(
                        request, body_blocks, tracker
                    )

            del schema_pool

            tracker.show(tag)
            self._log(f'Task end {tag}\n')

    def _run_oneway_fuzzing(self, request, body_schema_list):
        """ Run pre-configured fuzzing strategy without any feedback

        @param request: The request to fuzz
        @type  request: Request
        @param body_schema_list: A list of seed body schema
        @type  body_schema_list: List [BodySchema]

        @return: None
        @rtype:  None

        """
        # Configuration
        config_schema_fuzzer = {
            'max_combination': 10000,
            'max_propagation': 10000
        }
        config_schema_interp = {
            'get_wordbook_values': self._req_collection.candidate_values_pool.get_candidate_values,
            'get_examples_values': self._get_examples_values,
            'get_response_values': self._get_response_values,
            'fuzz_strategy': 'EX',
            'max_combination': 1,
            'use_examples_for_default': True,
            'use_response_for_default': True,
            'use_embedded_for_fuzzable': False,
            'use_wordbook_for_fuzzable': False
        }

        node_num = body_schema_list[-1].node_count
        if self._size_dep_budget:
            max_combination = max(200, 10 * node_num)
            pipeline_width = max(20, node_num)
        else:
            max_combination = self._fixed_budget_max_combination
            pipeline_width = self._fixed_budget_pipeline_width
        random_seed = 0

        self._log(f'#N: {node_num}, #max: {max_combination}, #width: {pipeline_width}')

        # Trackers
        ignore = set(
            self._req_collection.candidate_values_pool.get_candidate_values(
                primitives.FUZZABLE_STRING
            )
        )
        tracker_invalid_json = ResponseTracker(ignore, False, self._log)
        tracker_type = ResponseTracker(ignore, False, self._log)

        # INVALID JSON
        self._log('Task begin Invalid-JSON')
        self._run_invalid_json_task(
            request, body_schema_list, config_schema_fuzzer,
            config_schema_interp, tracker_invalid_json
        )

        tracker_invalid_json.show('Invalid-JSON')
        self._log('Task end Invalid-JSON\n')

        # STRUCT
        self._log('Task begin STRUCT-TYPE')
        schema_pool_structure = self._begin_struct_task(body_schema_list, config_schema_fuzzer,
                                                        pipeline_width, random_seed)

        # TYPE
        tested_schema_signs = set([])
        for schema_seed in schema_pool_structure:
            schema_pool_type = BodyFuzzer_Type(self._log, 'single').run(
                schema_seed, config_schema_fuzzer
            )
            random.Random(random_seed).shuffle(schema_pool_type)

            self._run_value_fuzzing_on_pool(request, schema_pool_type, config_schema_interp,
                                            tracker_type, max_combination, tested_schema_signs)
            del schema_pool_type

            if len(tested_schema_signs) >= max_combination:
                break

        tracker_type.show('STRUCT-TYPE')
        self._log('Task end STRUCT-TYPE')

    def _run_feedback_fuzzing(self, request, body_schema_list):
        """ Run pre-configured fuzzing strategy with some feedback

        @param request: The request to fuzz
        @type  request: Request
        @param body_schema_list: A list of seed body schema
        @type  body_schema_list: List [BodySchema]

        @return: None
        @rtype:  None

        """
        # Configuration
        config_schema_fuzzer = {
            'max_combination': 10000,
            'max_propagation': 10000
        }
        config_schema_interp = {
            'get_wordbook_values': self._req_collection.candidate_values_pool.get_candidate_values,
            'get_examples_values': self._get_examples_values,
            'get_response_values': self._get_response_values,
            'fuzz_strategy': 'EX',
            'max_combination': 1,
            'use_examples_for_default': True,
            'use_response_for_default': True,
            'use_embedded_for_fuzzable': False,
            'use_wordbook_for_fuzzable': False
        }

        node_num = body_schema_list[-1].node_count
        # budget_scale = int(node_num / 500) + 1
        budget_scale = 1
        if self._size_dep_budget:
            max_combination = max(200, budget_scale * 10 * node_num)
            pipeline_width = max(20, budget_scale * node_num)
        else:
            max_combination = self._fixed_budget_max_combination
            pipeline_width = self._fixed_budget_pipeline_width

        random_seed = 0
        self._log(f'#N: {node_num}, #max: {max_combination}, #width: {pipeline_width}')

        # Trackers
        ignore = set(
            self._req_collection.candidate_values_pool.get_candidate_values(
                primitives.FUZZABLE_STRING
            )
        )
        tracker_invalid_json = ResponseTracker(ignore, False, self._log)
        tracker_structure = ResponseTracker(ignore, False, self._log)
        tracker_type = ResponseTracker(ignore, False, self._log)

        # INVALID JSON
        self._log('Task begin Invalid-JSON')
        self._run_invalid_json_task(
            request, body_schema_list, config_schema_fuzzer,
            config_schema_interp, tracker_invalid_json
        )

        tracker_invalid_json.show('Invalid-JSON')
        self._log('Task end Invalid-JSON\n')

        # STRUCT
        self._log('Task begin Structure')
        schema_pool_structure = self._begin_struct_task(body_schema_list, config_schema_fuzzer,
                                                        pipeline_width, random_seed)

        num_valid = 0
        num_error = 0
        schema_pool_valid = []
        schema_pool_error = []

        for schema in schema_pool_structure:
            self._run_body_value_fuzzing(
                request, schema, config_schema_interp, tracker_structure
            )

            if num_valid < tracker_structure.num_valid:
                schema_pool_valid.append(schema)
                num_valid = tracker_structure.num_valid

            if num_error < tracker_structure.num_error_codes:
                schema_pool_error.append(schema)
                num_error = tracker_structure.num_error_codes

        del schema_pool_structure

        tracker_structure.show('Structure')
        self._log('Task end Structure\n')

        # TYPE
        self._log('Task begin Type')

        schema_pool_distinct_struct = self._filter_duplicate(
            body_schema_list[:-1] + schema_pool_valid + schema_pool_error
        )
        del schema_pool_valid
        del schema_pool_error

        tested_schema_signs = set([])

        for schema_seed in schema_pool_distinct_struct:
            schema_pool_type = BodyFuzzer_Type_Cheap(self._log).run(
                schema_seed, config_schema_fuzzer
            )[1:]
            random.Random(random_seed).shuffle(schema_pool_type)

            self._run_value_fuzzing_on_pool(request, schema_pool_type, config_schema_interp,
                                            tracker_type, max_combination, tested_schema_signs)
            del schema_pool_type

            if len(tested_schema_signs) >= max_combination:
                break

        for schema_seed in schema_pool_distinct_struct:
            schema_pool_type = BodyFuzzer_Type(self._log, 'single').run(
                schema_seed, config_schema_fuzzer
            )[1:]
            random.Random(random_seed).shuffle(schema_pool_type)

            self._run_value_fuzzing_on_pool(request, schema_pool_type, config_schema_interp,
                                            tracker_type, max_combination, tested_schema_signs)
            del schema_pool_type

            if len(tested_schema_signs) >= max_combination:
                break

        tracker_type.show('Type')
        self._log('Task end Type')

    def _run_invalid_json_task(self, request, body_schema_list, config_schema_fuzzer,
                               config_schema_interp, tracker):
        """ Helper function to run the INVALID-JSON task by running the
        Duplicate_Object fuzzing task on each body schema in the list

        @param request: The request whose body is being fuzzed
        @type  request: Request
        @param body_schema_list: List of body schemas to fuzz
        @type  body_schema_list: List[BodySchema]
        @param config_schema_fuzzer: The fuzzer's config
        @type  config_schema_fuzzer: Dict
        @param config_schema_interp: The config used during schema traversal
        @type  config_schema_interp: Dict
        @param tracker: The response tracker
        @type  tracker: ResponseTracker

        @return: None
        @rtype : None

        """
        for schema_seed in body_schema_list:
            schema_pool_invalid_json = BodyFuzzer_Duplicate_Object(self._log).run(
                schema_seed, config_schema_fuzzer
            )

            for schema in schema_pool_invalid_json:
                self._run_body_value_fuzzing(
                    request, schema, config_schema_interp, tracker
                )

    def _begin_struct_task(self, body_schema_list, config_schema_fuzzer, pipeline_width, random_seed):
        """ Helper function that begins the struct task by creating a schema pool from
        a Drop followed by a Select fuzzing task performed on each body schema.

        @param body_schema_list: List of body schemas to fuzz
        @type  body_schema_list: List[BodySchema]
        @param config_schema_fuzzer: The fuzzer's config
        @type  config_schema_fuzzer: Dict
        @param pipeline_width: The maximum schema width for the pipeline
        @type  pipeline_width: Int
        @param random_seed: Seed for the random number generator
        @type  random_seed: Int
        """
        schema_pool_drop_examples = []
        for schema_seed in body_schema_list[:-1]:
            schema_pool_drop_examples += BodyFuzzer_Drop(self._log, 'single').run(
                schema_seed, config_schema_fuzzer
            )
        random.Random(random_seed).shuffle(schema_pool_drop_examples)

        schema_pool_select_spec = BodyFuzzer_Select(self._log, 'path').run(
            body_schema_list[-1], config_schema_fuzzer
        )
        random.Random(random_seed).shuffle(schema_pool_select_spec)

        schema_pool_structure = self._filter_duplicate(
            body_schema_list[:-1] +
            schema_pool_drop_examples + schema_pool_select_spec
        )[:pipeline_width]

        return schema_pool_structure

    def _run_value_fuzzing_on_pool(self, request, schema_pool, config_schema_interp,
                                   tracker, max_combination, tested_schema_signs):
        """ Helper function that runs body value fuzzing on each unique schema in a schema pool

        @param request: The request whose body is being fuzzed
        @type  request: Request
        @param schema_pool: List of body schemas to run value fuzzing on
        @type  schema_pool: List[BodySchema]
        @param config_schema_interp: The config used during schema traversal
        @type  config_schema_interp: Dict
        @param tracker: The response tracker
        @type  tracker: ResponseTracker
        @param max_combination: The maximum combinations to fuzz
        @type  max_combination: Int
        @param tested_schema_signs: The signs of schemas that have already been tested
        @type  tested_schema_signs (IN/OUT): Set(str)

        @return: None
        @rtype : None

        """
        for schema in schema_pool:
            sign = schema.get_signature()
            if sign not in tested_schema_signs:
                self._run_body_value_fuzzing(
                    request, schema, config_schema_interp, tracker
                )
                tested_schema_signs.add(sign)
                if len(tested_schema_signs) >= max_combination:
                    break

    def _filter_duplicate(self, src_list):
        """ Filter out repeated body schemas in the list

        @param src_list: A list of body schemas
        @type  src_list: List

        @return: A list of body schemas without duplicates
        @rtype:  List

        """
        signatures = set([])

        def func_check_unique(schema):
            sign = schema.get_signature()
            if sign in signatures:
                return False
            else:
                signatures.add(sign)
                return True
        return list(filter(func_check_unique, src_list))

    def _run_body_value_fuzzing(self, request, body_schema, config, tracker):
        """ Do value fuzzing (rendering of the request body) and send the tests

        @param request: The request being fuzzed
        @type  request: Request
        @param body_schema: The body schema to be tested
        @type  body_schema: BodySchema
        @param config: Interpreter run-time configuration
        @type  config: Dict
        @param tracker: Response tracker
        @type  tracker: ResponseTracker

        @return: None
        @rtype:  None

        """
        body_blocks_fuzzed = body_schema.fuzz_body_blocks(config)
        for body_blocks in body_blocks_fuzzed:
            self._exec_request_with_new_body(request, body_blocks, tracker)

    def _refresh(self, last_request):
        """ Refresh server state and response mapping

        @param last_request: Last request to fuzz
        @type  last_request: Request

        @return: The new sequence that was sent during refresh
        @rtype:  Sequence

        """
        # replay the whole sequence except the last request
        new_seq = self._execute_start_of_sequence()

        # re-send the last request and analyze the response w.r.t body schema
        initial_response, response_to_parse = self._render_and_send_data(new_seq, last_request)

        if not initial_response:
            return None

        hints = self._map_response_to_current_body_schema(response_to_parse)

        if self._acc_response:
            for tag in hints:
                self._response_values[tag] = hints[tag]

        else:
            self._response_values = hints

        self._refresh_req = False
        RAW_LOGGING("Done refreshing the sequence")
        return new_seq

    def _set_refresh_req(self, request, response):
        """ Checks a request and response to see if a refresh should be triggered
        and sets the refresh_req member variable

        @param request: The request to check
        @type  request: Request
        @param response: The response to check
        @type  response: HttpResponse

        @return: None
        @rtype : None

        """
        self._refresh_req = request and request.is_consumer() and\
            request.is_resource_generator() and\
            response and response.has_valid_code()

    def _execute_start_of_sequence(self):
        """ Send all requests in the sequence up until the last request

        @return: None
        @rtype : None

        """
        # Copied from InvalidDynamicObjectChecker
        RAW_LOGGING("Re-rendering and sending start of sequence")
        new_seq = sequences.Sequence([])
        for request in self._sequence.requests[:-1]:
            new_seq = new_seq + sequences.Sequence(request)
            initial_response, response_to_parse = self._render_and_send_data(new_seq, request)

            # Check to make sure a bug wasn't uncovered while executing the
            # sequence
            if initial_response:
                if initial_response.has_bug_code():
                    self._print_suspect_sequence(new_seq, initial_response)
                    BugBuckets.Instance().update_bug_buckets(
                        new_seq, initial_response.status_code, origin=self.__class__.__name__
                    )

                if self._acc_response:
                    hints = self._map_response_to_current_body_schema(
                        response_to_parse
                    )
                    for tag in hints:
                        self._response_values[tag] = hints[tag]
        return new_seq

    def _map_response_to_current_body_schema(self, response):
        """ Extract values in a response based on the current body schema

        @param response: The response message
        @type  response: String

        @return: Tag/values mapping
        @rtype:  Dict

        """
        if not response or not response.has_valid_code():
            return {}

        # get the body (JSON)
        try:
            body = json.loads(response.json_body)
        except (json.JSONDecodeError, TypeError):
            return {}

        flat_body = flatten_json_object(body)

        hints = {}

        # keep all responses (not just w.r.t. the complete body schema)
        for tag in flat_body:
            if isinstance(flat_body[tag], list):
                hints[tag] = flat_body[tag]
            else:
                hints[tag] = [flat_body[tag]]

        return hints

    def _get_response_values(self, tag, hint=None):
        """ Return the values extracted from response

        @param tag: Parameter tag
        @type  tag: String
        @param hint: Used for looking up keywords and custom payloads
        @type  hint: Str

        @return: A list of values for the tag
        @rtype:  List

        """
        if self._response_values and tag in self._response_values:
            return self._response_values[tag]

        values = []
        if hint and self._keyword_response:
            values = self._get_response_values_by_keywords(hint)

        if not values and self._greedy_response:
            values = self._get_response_values_by_end_tag(tag)

        if not values and hint:
            values = self._get_custom_payload(hint)

        return values

    def _get_examples_values(self, tag):
        """ Return the values extracted from examples

        @param tag: Parameter tag
        @type  tag: String

        @return: A list of values for the tag
        @rtype:  List

        """
        if self._examples_values and tag in self._examples_values:
            return self._examples_values[tag]

        return []

    def _get_response_values_by_end_tag(self, tag):
        """ Return the values from response based on the last tag term

        @param tag: Parameter tag
        @type  tag: String

        @return: A list of values for the tag
        @rtype:  List

        """
        if not self._response_values:
            return []

        # replace original tags by its end term
        new_pool = {}
        for rsp_tag in self._response_values:
            end_tag = rsp_tag.split('_')[-1]
            new_pool[end_tag] = self._response_values[rsp_tag]

        # check if there is a match
        target_tag = tag.split('_')[-1]
        if target_tag in new_pool:
            return new_pool[target_tag]
        else:
            return []

    def _get_response_values_by_keywords(self, hint):
        """ Return the values from response based on the given hint/keyword

        @param hint: Hint/keyword in the response
        @type  hint: String

        @return: A list of values having the hint
        @rtype:  List

        """
        if not self._response_values:
            return []

        # check if the hint is a keyword
        if hint in self._keywords_for_response:
            value_to_search = self._keywords_for_response[hint]
        else:
            return []

        # check if any values from the response contains a keyword
        for rsp_tag in self._response_values:
            values = self._response_values[rsp_tag]
            for val in values:
                if str(value_to_search) in str(val):
                    return [val]

        return []

    def _get_custom_payload(self, tag):
        """ Return the custom payload of the tag if provided

        @param tag: Parameter tag
        @type  tag: String

        @return: A list of custom payload of the tag
        @rtype:  List

        """
        current_fuzzable_tag = tag.split('_')[-1]
        try:
            custom_payload_values = self._req_collection.candidate_values_pool.get_candidate_values(
                primitives.CUSTOM_PAYLOAD
            )
            current_fuzzable_values = custom_payload_values[current_fuzzable_tag]
            if isinstance(current_fuzzable_values, list):
                return current_fuzzable_values
            else:
                return [current_fuzzable_values]
        except Exception:
            return []

    def _get_custom_payload_uuid4_suffix(self):
        """ Return a dictionary of UUID4 suffix/value pairs

        @return: UUID4 suffix/value pairs
        @rtype:  Dict

        """
        try:
            custom_payload_uuid4_suffix_values = self._req_collection.\
                candidate_values_pool.get_candidate_values(
                    primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX
                )
            return custom_payload_uuid4_suffix_values
        except Exception:
            return {}

    def _exec_request_with_new_body(
            self, request, body_blocks, tracker, valid_is_violation=False):
        """ Render and send the new request and analyze the response

        @param request: Seed request
        @type  request: Request
        @param body_blocks: Definition (request blocks) of the new body
        @type  body_blocks: List
        @param tracker: Response tracker for this run
        @type  tracker: ResponseTracker
        @param valid_is_violation: If valid response is violation
        @type  valid_is_violation: Bool

        @return: None
        @rtype:  None

        """
        # substitute to the original request
        new_request = substitute_body(request, body_blocks)
        if new_request is None:
            self._log(f"Failed to substitute body for request {request.endpoint}.")
            return

        seq = copy(self._sequence)
        cnt = 0

        # iterate through different value combinations
        for rendered_data, parser in new_request.render_iter(
            self._req_collection.candidate_values_pool
        ):
            # check time budget
            if Monitor().remaining_time_budget <= 0:
                raise TimeOutException('Exceed Timeout')

            # stop fuzzing when reaching the bound
            if cnt > int(Settings().max_combinations):
                break
            cnt += 1

            # stop fuzzing when reaching the global bound
            if self._global_bound > 0 and self._global_count > self._global_bound:
                break
            self._global_count += 1

            # refresh the sequence to make sure the resource is not garbage collected
            if self._refresh_req:
                seq = self._refresh(request)

            # render the data
            rendered_data = seq.resolve_dependencies(rendered_data)

            # substitute if there is UUID suffix
            original_rendered_data = rendered_data
            uuid4_suffix_dict = self._get_custom_payload_uuid4_suffix()
            for uuid4_suffix in uuid4_suffix_dict:
                suffix = uuid4_suffix_dict[uuid4_suffix]
                len_suffix = len(suffix)
                # need the query to partition path and body
                try:
                    partition = rendered_data.index('?')
                    if suffix in rendered_data[:partition]:
                        new_val_start = rendered_data[:partition].index(suffix)
                        if new_val_start + len_suffix + 10 > partition:
                            self._log('unexpected uuid')
                            continue
                        new_val = rendered_data[new_val_start:
                                                new_val_start + len_suffix + 10]

                        # find all occurence in the body
                        suffix_in_body = [
                            m.start() for m in re.finditer(suffix, rendered_data)
                        ][1:]
                        for si in suffix_in_body:
                            old_val = rendered_data[si: si + len_suffix + 10]
                            rendered_data = rendered_data.replace(
                                old_val, new_val)
                except Exception:
                    rendered_data = original_rendered_data

            # send out the request
            response = self._send_request(parser, rendered_data)
            request_utilities.call_response_parser(parser, response)
            self._set_refresh_req(request, response)

            if not response or not response.status_code:
                self._log('ERROR: no response received')
                continue

            # analyze response -- coverage
            tracker.process_response(response)

            if self._acc_response:
                hints = self._map_response_to_current_body_schema(response)
                for tag in hints:
                    self._response_values[tag] = hints[tag]

            # analyze response -- error
            if self._rule_violation(seq, response, valid_is_violation):
                # Append the new request to the sequence before filing the bug
                seq.replace_last_sent_request_data(rendered_data, parser, response)
                err_seq = sequences.Sequence(seq.requests[:-1] + [new_request])
                err_seq.set_sent_requests_for_replay(seq.sent_request_data_list)
                self._print_suspect_sequence(err_seq, response)

                bug_info = self._buckets.add_bug(request, rendered_data)
                if bug_info is not None:
                    error_str = bug_info[0]
                    new_body = bug_info[1]
                    log_str = f'{error_str}\n{new_body}'
                    BugBuckets.Instance().update_bug_buckets(
                        err_seq, response.status_code, origin=self.__class__.__name__, checker_str=error_str, additional_log_str=log_str
                    )
                self._refresh_req = True

    class FuzzTask():
        """ Helper class for a fuzz task """

        def __init__(self, fuzzer, fuzzer_config={}, interp_config={}):
            """ Initialize a fuzz task

            @param fuzzer: Fuzzer
            @type  fuzzer: Object
            @param fuzzer_config: Fuzzer configuration
            @type  fuzzer_config: Dict
            @param interp_config: Interpreter configuration
            @type  interp_config: Dict

            @return: None
            @rtype:  None

            """
            self._fuzzer = fuzzer
            self._fuzzer_config = fuzzer_config.copy()
            self._interp_config = interp_config.copy()

        @property
        def fuzzer(self):
            """ Return the task fuzzer

            @return: Fuzzer
            @rtype:  Object

            """
            return self._fuzzer

        @property
        def fuzzer_config(self):
            """ Return the fuzzer configuration

            @return: Fuzzer configuration
            @rtype:  Dict

            """
            return self._fuzzer_config

        @property
        def interp_config(self):
            """ Return the interpreter configuration

            @return: Interpreter configuration
            @rtype:  Dict

            """
            return self._interp_config
