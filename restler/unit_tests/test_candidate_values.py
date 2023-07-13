import unittest
import os
import datetime
from datetime import datetime as dt
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
    def tearDown(self):
        RestlerSettings.TEST_DeleteInstance()

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
        fuzzable_string = primitives.restler_fuzzable_string("fuzzstring", quoted=False, examples=[])
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
        fuzzable_int = primitives.restler_fuzzable_int("20", quoted=False, examples=[])
        override_value_gen["restler_fuzzable_int"] = None
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

    def test_date_examples(self):
        """Test that adjusting date examples to make them current works"""
        # Candidate pool creation requires the RestlerSettings() instance to be created
        s = RestlerSettings({})
        pool = CandidateValuesPool()
        start = dt(2022, 8, 28)
        end = start + datetime.timedelta(days = 7)

        def test_dates(example_test_date, expected_new_date):
            # test that these are updated correctly and are between [today, today + 7]
            x = pool._get_current_date_from_example(example_test_date, end)
            self.assertEqual(x, expected_new_date)

        test_dates_with_expected = [
            ("2018-01-01T12:10:00010Z", "2022-09-04T12:10:00010Z"),
            ("2018-06-12T22:05:09Z", "2022-09-04T22:05:09Z"),
            ("2018-01-01", "2022-09-04"),
            ("12/09/2018", "09/04/2022"),
            ("1/09/2019", "09/04/2022"),
            ("1/8/2019", "09/04/2022"),
            ("2/2/2020 8:34:47 PM","09/04/2022 8:34:47 PM"),
            ("8/11/2017 9:05:00 PM", "09/04/2022 9:05:00 PM"),
            ("8/2/2018 4:08:12 AM (UTC)", "09/04/2022 4:08:12 AM (UTC)")
        ]
        for (date, expected_date) in test_dates_with_expected:
            test_dates(date, expected_date)

        # Test example None is returned unmodified
        x = pool._get_current_date_from_example(None, end)
        self.assertTrue(x is None)
        pass
