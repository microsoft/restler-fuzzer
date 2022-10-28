import unittest
import os
import sys
import importlib
import importlib.util
import json

from engine.fuzzing_parameters.param_combinations import *
from engine.fuzzing_parameters.fuzzing_config import FuzzingConfig

import restler_settings
from restler_settings import Settings
from restler_settings import UninitializedError as UninitializedSettingsError
from engine.core.preprocessing import parse_grammar_schema
from engine.core.requests import GrammarRequestCollection

from engine.fuzzing_parameters.parameter_schema import HeaderList
from engine.fuzzing_parameters.parameter_schema import QueryList

def get_grammar_file_path(grammar_file_name):
    Test_File_Directory = os.path.join(
        os.path.dirname(__file__), 'grammar_schema_test_files'
    )
    return os.path.join(Test_File_Directory, grammar_file_name)

def get_python_grammar(grammar_name):
    python_grammar_file_name = f"{grammar_name}.py"
    grammar_file_path = get_grammar_file_path(python_grammar_file_name)

    sys.path.append(os.path.dirname(grammar_file_path))
    grammar = importlib.import_module(grammar_name)
    req_collection = getattr(grammar, "req_collection")

    return req_collection

def set_grammar_schema(grammar_file_name, request_collection):
    grammar_file_path = get_grammar_file_path(grammar_file_name)
    schema_json=''
    with open(grammar_file_path, 'r') as grammar:
        schema_json = json.load(grammar)
    parse_grammar_schema(schema_json, request_collection)

class SchemaParserTest(unittest.TestCase):

    maxDiff = None

    def setup(self):
        try:
            self.settings = Settings()
        except UninitializedSettingsError:
            self.settings = restler_settings.RestlerSettings({})

    def tearDown(self):
        restler_settings.RestlerSettings.TEST_DeleteInstance()

    def generate_new_request(self, req, headers_schema, query_schema, body_schema, use_get_blocks=False):
        fuzzing_config = FuzzingConfig()

        if use_get_blocks:
            query_blocks = query_schema.get_blocks()
        else:
            query_blocks = query_schema.get_original_blocks(fuzzing_config)
        new_request = req.substitute_query(query_blocks)
        self.assertTrue(new_request is not None)

        if use_get_blocks:
            header_blocks = headers_schema.get_blocks()
        else:
            header_blocks = headers_schema.get_original_blocks(fuzzing_config)

        new_request = new_request.substitute_headers(header_blocks)
        self.assertTrue(new_request is not None)

        if body_schema is not None:
            body_schema.set_config(fuzzing_config)  # This line is required for legacy reasons
            if use_get_blocks:
                body_blocks = body_schema.get_blocks()
            else:
                body_blocks = body_schema.get_original_blocks(fuzzing_config)

            new_request = new_request.substitute_body(body_blocks)
            self.assertTrue(new_request is not None)

        return new_request

    def check_equivalence(self, original_req, generated_req, req_collection, fuzzables_equal=True, custom_payloads_equal=True):
        # Fuzzables equal
        original_fuzzables = list(filter(lambda x: 'restler_fuzzable' in x[0], original_req.definition))
        generated_fuzzables = list(filter(lambda x: 'restler_fuzzable' in x[0], generated_req.definition))

        if fuzzables_equal:
            self.assertEqual(original_fuzzables, generated_fuzzables)
        else:
            self.assertNotEqual(original_fuzzables, generated_fuzzables)

        # Custom payloads equal
        original_custom_payloads = list(filter(lambda x: 'restler_custom_payload' in x[0], original_req.definition))
        generated_custom_payloads = list(filter(lambda x: 'restler_custom_payload' in x[0], generated_req.definition))
        if custom_payloads_equal:
            self.assertEqual(original_custom_payloads, generated_custom_payloads)
        else:
            self.assertNotEqual(original_custom_payloads, generated_custom_payloads)

        # TODO: enums equal

        # Payloads equal
        original_rendered_data,_,_,_ = next(original_req.render_iter(req_collection.candidate_values_pool))
        generated_rendered_data,_,_,_ = next(generated_req.render_iter(req_collection.candidate_values_pool))

        original_rendered_data = original_rendered_data.replace("\r\n", "")

        original_rendered_data = original_rendered_data.replace("\n", "")
        original_rendered_data = original_rendered_data.replace(" ", "")
        generated_rendered_data = generated_rendered_data.replace("\r\n", "")

        generated_rendered_data = generated_rendered_data.replace("\n", "")
        generated_rendered_data = generated_rendered_data.replace(" ", "")
        if fuzzables_equal and custom_payloads_equal:
            self.assertEqual(original_rendered_data, generated_rendered_data)
        else:
            self.assertNotEqual(original_rendered_data, generated_rendered_data)
        return original_rendered_data, generated_rendered_data

    def test_simple_request(self):
        # This test checks that the json schema has the expected properties, and
        # the request payload is correctly generated from this schema.
        def check_body_schema_properties(req):
            self.assertTrue(req.body_schema is not None)
            schema_members = req.body_schema.schema.members
            self.assertTrue(len(schema_members) == 2)
            self.assertEqual(schema_members[0].name, "id")
            self.assertEqual(schema_members[0].value.is_required, False)
            self.assertEqual(schema_members[0].value.content, "fuzzstring")
            self.assertEqual(schema_members[1].name, "Person")
            self.assertEqual(schema_members[1].is_required, False)
            customer_members = schema_members[1].value.members
            self.assertTrue(len(customer_members) == 2)
            self.assertEqual(customer_members[0].name, "name")
            self.assertEqual(customer_members[0].is_required, True)
            self.assertEqual(customer_members[0].value.content, "fuzzstring")
            self.assertEqual(customer_members[1].name, "address")
            self.assertEqual(customer_members[1].is_required, False)
            self.assertEqual(customer_members[1].value.content, "fuzzstring")

        def check_query_schema_properties(req):
            self.assertTrue(req.query_schema is not None)
            schema_members = req.query_schema.param_list
            self.assertTrue(len(schema_members) == 1)
            self.assertEqual(schema_members[0].key, "api-version")
            self.assertEqual(schema_members[0].is_required, True)
            self.assertEqual(schema_members[0].content.content, "fuzzstring")

        def check_headers_schema_properties(req, num_headers=None):
            self.assertTrue(req.headers_schema is not None)
            header_members = req.headers_schema.param_list
            if num_headers is not None:
                self.assertTrue(len(header_members) >= num_headers)
            self.assertEqual(header_members[0].key, "schema-version")
            self.assertEqual(header_members[0].is_required, False)
            self.assertEqual(header_members[0].content.content, "fuzzstring")

        def filter_fuzzables(req_definition):
            return filter(lambda x : 'restler_fuzzable' in x[0] , req_definition)

        self.setup()

        grammar_name = "simple_swagger_all_param_types_grammar"
        schema_json_file_name = f"{grammar_name}.json"

        request_collection = get_python_grammar(grammar_name)

        set_grammar_schema(schema_json_file_name, request_collection)

        # 1. Confirm that all of the parameters are present in the schema.
        for idx, req in enumerate(request_collection):
            has_body = (idx == 0)
            num_headers = 2 if has_body else 1
            if has_body:
                check_body_schema_properties(req)
            check_headers_schema_properties(req, num_headers=num_headers)
            check_query_schema_properties(req)

            # 2. Generate the Python grammar from this schema, and confirm it matches
            # the expected Python grammar (generated by the RESTler compiler)
            # Go through and generate the body, query, and headers
            # then, call 'substitute' on the request.
            # Then, make sure they match the original request.
            # This is a "round trip" test for the request.
            generated_req = self.generate_new_request(req, req.headers_schema, req.query_schema, req.body_schema)

            # Checking for equality is not going to work because of the compiler
            # feature to "merge" the grammars.  We will have to validate as follows:
            # 1) The same 'fuzzable' and 'custom payload' and 'enum' entries are there
            # 2) the generated payload is the same.

            self.check_equivalence(req, generated_req, request_collection)

            # Now generate the request with required parameters only
            combination_settings = {
                "max_combinations": 1,
                "param_kind": "optional"
            }
            req_current = req
            req_current = next(req_current.get_header_param_combinations(combination_settings))
            req_current = next(req_current.get_query_param_combinations(combination_settings))
            if req.body_schema:
                req_current = next(req_current.get_body_param_combinations(combination_settings))
            required_only_generated_req = req_current
            original_rendering, generated_rendering =\
                self.check_equivalence(req, required_only_generated_req, request_collection, fuzzables_equal=False)

            # Confirm that none of the optional parameters are present in the generated request.
            optional_param_names = {
                0: ['schema-version', 'id', 'address'],
                1: ['schema-version', 'view-option']
            }

            for optional_param in optional_param_names[idx]:
                # The original rendering currently has all parameters, optional and required.
                self.assertTrue(optional_param in original_rendering, optional_param)
                self.assertFalse(optional_param in generated_rendering, optional_param)

    def test_schema_pool_no_fuzzing(self):
        """
        This test checks that the schema pool returns the correct schema when no
        fuzzing has been requested.
        """
        self.setup()
        grammar_name = "simple_swagger_all_param_types_grammar"
        schema_json_file_name = f"{grammar_name}.json"

        request_collection = get_python_grammar(grammar_name)

        set_grammar_schema(schema_json_file_name, request_collection)
        req_with_body = next(iter(request_collection))

        # Fuzz the body using the base class for fuzzing the schema, which should be a no-op.
        schema_pool = JsonBodySchemaFuzzerBase().run(req_with_body.body_schema)

        self.assertEqual(len(schema_pool), 1)

        generated_req = self.generate_new_request(req_with_body, req_with_body.headers_schema,
                                                  req_with_body.query_schema, schema_pool[0])
        self.check_equivalence(req_with_body, generated_req, request_collection)

        # Now generate combinations of the body properties according to the default strategy
        schema_pool_2 = JsonBodyPropertyCombinations().run(req_with_body.body_schema)

        # TODO: Confirm the expected combinations are in the schema pool.
        self.assertTrue(len(schema_pool_2) > 1)

        pass

    def test_schema_with_null_example(self):
        """Regression test for generating a python grammar from a schema with a null example. """
        self.setup()
        grammar_name = "null_test_example_grammar"
        schema_json_file_name = f"{grammar_name}.json"

        request_collection = get_python_grammar(grammar_name)

        set_grammar_schema(schema_json_file_name, request_collection)
        req_with_body = next(iter(request_collection))
        print(f"req{req_with_body.endpoint} {req_with_body.method}")

        # Just go through and get all schema combinations.  This makes sure there are no crashes.
        for x, is_example in req_with_body.get_schema_combinations(use_grammar_py_schema=False):
            self.assertTrue(len(x.definition) > 0)

    def test_schema_with_uuid4_suffix_example(self):
        """Regression test for generating a python grammar from a schema with a uuid4_suffix in the body. """
        self.setup()
        grammar_name = "uuidsuffix_test_grammar"
        schema_json_file_name = f"{grammar_name}.json"

        request_collection = get_python_grammar(grammar_name)

        set_grammar_schema(schema_json_file_name, request_collection)
        req_with_body = next(iter(request_collection))
        print(f"req{req_with_body.endpoint} {req_with_body.method}")

        # Just go through and get all schema combinations.  This makes sure there are no crashes.
        for x, is_example in req_with_body.get_schema_combinations(use_grammar_py_schema=False):
            self.assertTrue(len(x.definition) > 0)

    def test_schema_with_all_supported_writers_example(self):
        """Regression test for all the ways dynamic objects can appear in the json grammar.
         This test does a 'round trip' from the json to the original Python grammar and confirms
         the payloads are identical. """
        pass

    def test_all_data_types_request(self):

        def test_grammar(grammar_name, dictionary_file_name=None, all_params_required=False):
            schema_json_file_name = f"{grammar_name}.json"

            request_collection = get_python_grammar(grammar_name)

            set_grammar_schema(schema_json_file_name, request_collection)

            if dictionary_file_name is not None:
                custom_mutations = json.load(open(dictionary_file_name, encoding='utf-8'))
                request_collection.set_custom_mutations(custom_mutations, None, None)
                pass
            # Check the equivalence of the request in grammar.py (generated by the compiler)
            # with the engine-generated request.
            for idx, req in enumerate(request_collection):

                # 2. Generate the Python grammar from this schema, and confirm it matches
                # the expected Python grammar (generated by the RESTler compiler)
                # Go through and generate the body, query, and headers
                # then, call 'substitute' on the request.
                # Then, make sure they match the original request.
                # This is a "round trip" test for the request.
                generated_req = self.generate_new_request(req, req.headers_schema, req.query_schema, req.body_schema)

                # Checking for equality is not going to work because of the compiler
                # feature to "merge" the grammars.  We will have to validate as follows:
                # 1) The same 'fuzzable' and 'custom payload' and 'enum' entries are there
                # 2) the generated payload is the same.

                self.check_equivalence(req, generated_req, request_collection)

                # Now generate the request with required parameters only
                combination_settings = {
                    "max_combinations": 1,
                    "param_kind": "optional"
                }
                req_current = req
                req_current = next(req_current.get_header_param_combinations(combination_settings))
                req_current = next(req_current.get_query_param_combinations(combination_settings))
                if req.body_schema:
                    req_current = next(req_current.get_body_param_combinations(combination_settings))
                required_only_generated_req = req_current

                if all_params_required:
                    original_rendering, generated_rendering =\
                        self.check_equivalence(req, required_only_generated_req, request_collection, fuzzables_equal=True)

        self.setup()

        grammar_names = [
            "simple_swagger_all_param_data_types_grammar",
            "simple_swagger_all_param_data_types_local_examples_grammar",
            "simple_swagger_with_annotations_grammar",
            "demo_server_grammar",
            "substitute_body_regression_test_grammar"
             # TODO: enable this after abstracting uuid suffix in the equivalence check
             # "simple_swagger_annotations_uuid4_suffix" # todo rename 'grammar'
        ]

        dict_file_name = get_grammar_file_path("simple_swagger_all_param_types_dict.json")
        for grammar_name in grammar_names:
            test_required = "demo_server" not in grammar_name
            test_grammar(grammar_name, dict_file_name, all_params_required=test_required)

    def test_schema_with_readonly_parameters(self):
        """Regression test for readonly parameters.  They should be filtered out when RESTler is
        generating combinations, but should not be filtered from example payloads (where all
        specified parameters should be included)."""
        self.setup()
        grammar_name = "readonly_test_grammar"
        schema_json_file_name = f"{grammar_name}.json"

        request_collection = get_python_grammar(grammar_name)

        set_grammar_schema(schema_json_file_name, request_collection)
        req_with_body = next(iter(request_collection))
        print(f"req{req_with_body.endpoint} {req_with_body.method}")

        combinations_count = 0
        for x, is_example in req_with_body.get_schema_combinations(use_grammar_py_schema=False):
            rendered_data,_,_,_ = next(x.render_iter(request_collection.candidate_values_pool))
            self.assertTrue("\"id\"" not in rendered_data)
            self.assertTrue("\"person\"" in rendered_data)
            self.assertTrue("\"name\"" in rendered_data)
            self.assertTrue("\"address\"" in rendered_data)
            combinations_count += 1

        # Confirm both all parameters and only required parameters were tested.
        # This also tests that the required parameters are correctly not filtered out
        self.assertEqual(combinations_count, 2)
