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

    # The line below is required to avoid key errors on the auth token
    # TODO: remove this constraint from the code, so the token refresh grammar element
    # can also be tested here.
    req_collection.remove_authentication_tokens()
    return req_collection

def set_grammar_schema(grammar_file_name, request_collection):
    grammar_file_path = get_grammar_file_path(grammar_file_name)
    schema_json=''
    with open(grammar_file_path, 'r') as grammar:
        schema_json = json.load(grammar)
    parse_grammar_schema(schema_json, request_collection)

class SchemaParserTest(unittest.TestCase):

    def setup(self):
        try:
            self.settings = Settings()
        except UninitializedSettingsError:
            self.settings = restler_settings.RestlerSettings({})

    def tearDown(self):
        restler_settings.RestlerSettings.TEST_DeleteInstance()

    def generate_new_request(self, req, headers_schema, query_schema, body_schema):
        fuzzing_config = FuzzingConfig()

        query_blocks = query_schema.get_original_blocks(fuzzing_config)
        new_request = req.substitute_query(query_blocks)
        self.assertTrue(new_request is not None)

        header_blocks = headers_schema.get_original_blocks(fuzzing_config)
        new_request = new_request.substitute_headers(header_blocks)
        self.assertTrue(new_request is not None)

        if body_schema is not None:
            body_schema.set_config(fuzzing_config) # This line is required for legacy reasons
            body_blocks = body_schema.get_original_blocks(fuzzing_config)
            new_request = new_request.substitute_body(body_blocks)
            self.assertTrue(new_request is not None)

        return new_request

    def check_equivalence(self, original_req, generated_req, req_collection, equal=True):
        # Fuzzables equal
        original_fuzzables=list(filter(lambda x : 'restler_fuzzable' in x[0] , original_req.definition))
        generated_fuzzables=list(filter(lambda x : 'restler_fuzzable' in x[0] , generated_req.definition))

        if equal:
            self.assertEqual(original_fuzzables, generated_fuzzables)
        else:
            self.assertNotEqual(original_fuzzables, generated_fuzzables)

        # TODO: enums equal

        # Payloads equal
        original_rendered_data,_,_ = next(original_req.render_iter(req_collection.candidate_values_pool))
        generated_rendered_data,_,_ = next(generated_req.render_iter(req_collection.candidate_values_pool))

        original_rendered_data = original_rendered_data.replace("\r\n", "")

        original_rendered_data = original_rendered_data.replace("\n", "")
        original_rendered_data = original_rendered_data.replace(" ", "")
        generated_rendered_data = generated_rendered_data.replace("\r\n", "")

        generated_rendered_data = generated_rendered_data.replace("\n", "")
        generated_rendered_data = generated_rendered_data.replace(" ", "")
        if equal:
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

