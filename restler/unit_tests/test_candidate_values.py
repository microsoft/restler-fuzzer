import unittest
import os

from engine.primitives import CandidateValues, CandidateValuesPool
from restler_settings import RestlerSettings
from engine.core.requests import Request
import engine.primitives as primitives
import engine.core.requests as requests
from engine.errors import InvalidDictionaryException
import engine.core.request_utilities as request_utilities
from checkers.invalid_value_checker import get_test_values
import typing


class CandidateValuesTest(unittest.TestCase):

    def test_candidate_values(self):

        generated_strings = ["gen_1st", "gen_2nd"]

        def generate_string(**kwargs):
            for x in generated_strings:
                yield x

        """Test the scenario used by the invalid values checker."""
        user_dict = {
            "restler_fuzzable_string": ["1st", "2nd"],
            "restler_fuzzable_int": ["1", "2"],
            "restler_custom_payload": {
                "first_custom": ["first_payload"],
                "second_custom": ["second_payload"]
            }
        }

        override_value_gen = {
            "restler_fuzzable_string": generate_string
        }

        # Candidate pool creation requires the RestlerSettings() instance to be created
        s = RestlerSettings({})

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        checkers_file_dir = os.path.join(current_file_dir, "..", "checkers")
        file_path = os.path.join(checkers_file_dir, "invalid_value_checker_value_gen.py")
        fuzzable_string = primitives.restler_fuzzable_string("fuzzstring", is_quoted=False, examples=[])
        req_definition = [fuzzable_string]
        temp_req = Request(req_definition)

        # Value generators only specified
        tv = get_test_values(2, temp_req, {}, file_path, override_value_generators=override_value_gen)
        tv=list(tv)
        self.assertEqual(tv, ["gen_1st", "gen_2nd"])

        # Dictionary and value generators specified
        tv = get_test_values(5, temp_req, user_dict, file_path, override_value_generators=override_value_gen)
        tv=list(tv)
        self.assertEqual(tv, ["1st", "2nd", "gen_1st", "gen_2nd", "gen_1st"])

        # Dictionary only specified
        tv = get_test_values(5, temp_req, user_dict, None)
        tv=list(tv)
        self.assertEqual(tv, ["1st", "2nd"])

        # No dictionary or generator value
        empty_value_gen = {
            "restler_fuzzable_string": None
        }
        try:
            # This should throw an exception
            tv = get_test_values(5, temp_req, user_dict, file_path, override_value_generators=empty_value_gen)
            tv = list(tv)
        except InvalidDictionaryException:
            pass

        # Default generators with 'int' in request block, which is not present there.
        # Expected: the string generator should be used.
        fuzzable_int = primitives.restler_fuzzable_int("20", is_quoted=False, examples=[])

        req_definition = [fuzzable_int]
        temp_req = Request(req_definition)
        tv = get_test_values(4, temp_req, user_dict, file_path, override_value_generators=override_value_gen)
        tv = list(tv)
        self.assertEqual(tv, ["1", "2", "gen_1st", "gen_2nd"])

        # No user specified value generator provided
        req_definition = [fuzzable_int]
        temp_req = Request(req_definition)

        # When there is no value generator file path, use the default (string) value generator up to the budget
        # Here, the user dictionary does specify an integer.
        # Since no value generators were specified the override value generator is not used.
        tv = get_test_values(4, temp_req, user_dict, None, override_value_generators=override_value_gen)
        tv = list(tv)
        self.assertEqual(tv, ["1", "2"])
