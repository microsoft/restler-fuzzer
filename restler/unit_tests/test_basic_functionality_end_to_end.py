# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Runs functional tests, which invoke the RESTler engine and check the RESTler output logs
for correctness.

When new baseline logs are necessary due to known breaking changes in the logic, a run that
matches the test should be run manually and the appropriate logs should be replaced in the
unit_tests/log_baseline_test_files directory. Each log is named <test-type_log-type.txt>

"""
import unittest
import os
import glob
import shutil
import subprocess
import json
import utils.logger as logger
import utils.import_utilities as import_utilities
import utils.logging.trace_db as trace_db
from utils.logging.serializer_base import *
from collections import namedtuple
from pathlib import Path
from test_servers.log_parser import *

Test_File_Directory = os.path.join(
    os.path.dirname(__file__), 'log_baseline_test_files'
)

Authentication_Test_File_Directory = os.path.join(
    os.path.dirname(__file__), 'authentication_test_files'
)

Restler_Path = os.path.join(os.path.dirname(__file__), '..', 'restler.py')


Common_Settings_No_Auth = [
    "python", "-B", Restler_Path, "--use_test_socket",
    '--custom_mutations', f'{os.path.join(Test_File_Directory, "test_dict.json")}',
    "--garbage_collection_interval", "30", "--host", "unittest",
]

Common_Settings = Common_Settings_No_Auth + [
     "--token_refresh_cmd", f'python {os.path.join(Authentication_Test_File_Directory, "unit_test_server_auth.py")}',
     "--token_refresh_interval", "10"
]

## TODO: Share constants with unit_test_server?
LOCATION_AUTHORIZATION_TOKEN = 'valid_location_unit_test_token'
MODULE_AUTHORIZATION_TOKEN = 'valid_module_unit_test_token'
CMD_AUTHORIZATION_TOKEN = 'valid_unit_test_token'


class FunctionalityTests(unittest.TestCase):
    def get_experiments_dir(self):
        """ Returns the most recent experiments directory that contains the restler logs

        @return: The experiments dir
        @rtype : Str

        """
        results_dir = os.path.join(os.getcwd(), 'RestlerResults')
        # Return the newest experiments directory in RestlerResults
        return max(glob.glob(os.path.join(results_dir, 'experiment*/')), key=os.path.getmtime)

    def get_network_log_path(self, dir, log_type):
        """ Returns the path to the network log of the specified type

        @param dir: The directory that contains the log
        @type  dir: Str
        @param log_type: The type of network log to get
        @type  log_type: Str

        @return: The path to the network log
        @rtype : Str

        """
        return glob.glob(os.path.join(dir, 'logs', f'network.{log_type}.*.1.txt'))[0]

    def run_restler_engine(self, args, failure_expected=False):
        result = subprocess.run(args, capture_output=True)
        if failure_expected:
            return
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode} {result.stdout}")

    def run_abc_smoke_test(self, test_file_dir, grammar_file_name, fuzzing_mode, settings_file=None, dictionary_file_name=None,
                           failure_expected=False, common_settings=Common_Settings,
                           enable_checkers=None):
        grammar_file_path = os.path.join(test_file_dir, grammar_file_name)
        if dictionary_file_name is None:
            dictionary_file_name = "abc_dict.json"
        dict_file_path = os.path.join(test_file_dir, dictionary_file_name)
        args = common_settings + [
        '--fuzzing_mode', f"{fuzzing_mode}",
        '--restler_grammar', f'{grammar_file_path}',
        '--custom_mutations', f'{dict_file_path}'
        ]
        if enable_checkers is not None:
            args = args + ['--enable_checkers', f'{enable_checkers}']
        if settings_file:
            if Path(settings_file).exists():
                settings_file_path = settings_file
            else:
                settings_file_path = os.path.join(test_file_dir, settings_file)
            args = args + ['--settings', f'{settings_file_path}']
        self.run_restler_engine(args, failure_expected=failure_expected)

    def tearDown(self):
        try:
            shutil.rmtree(self.get_experiments_dir())
        except Exception as err:
            print(f"tearDown function failed: {err!s}.\n"
                  "Experiments directory was not deleted.")

    def test_location_auth_test(self):
        """ This test is equivalent to test_abc_minimal_smoke_test except we use the token location authentication mechanism
            and validate that RESTler uses the LOCATION_AUTHORIZATION_TOKEN
        """
        settings_file_path = os.path.join(Authentication_Test_File_Directory, "token_location_authentication_settings.json")
        ## Create a new, temporary settings file with reference to full path to token location
        new_settings_file_path = os.path.join(Authentication_Test_File_Directory, "tmp_token_location_authentication_settings.json")
        try:
            with open(settings_file_path, 'r') as file:
                settings = json.loads(file.read())
                settings["authentication"]["token"]["location"] = os.path.join(Authentication_Test_File_Directory, settings["authentication"]["token"]["location"])
                json_settings = json.dumps(settings)
                with open(new_settings_file_path, "w") as outfile:
                    outfile.write(json_settings)
            self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py", "directed-smoke-test", settings_file=new_settings_file_path, common_settings=Common_Settings_No_Auth)
        finally:
            ## Clean up temporary settings file
            if os.path.exists(new_settings_file_path):
                os.remove(new_settings_file_path)

        experiments_dir = self.get_experiments_dir()

        ## Make sure all requests were successfully rendered.  This is because the comparisons below do not
        ## take status codes into account
        ## Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 5)
                self.assertLessEqual(total_requests_sent, 14)
                test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
                ## Validate that LOCATION_AUTHORIZATION_TOKEN is used in request headers
                self.assertTrue(test_parser.validate_auth_tokens(LOCATION_AUTHORIZATION_TOKEN))
        except TestFailedException:
            self.fail("Smoke test with token location auth failed")

    def test_module_no_data_auth(self):
        """ This test is equivalent to test_abc_minimal_smoke_test except we use the token module authentication mechanism
            and validate that RESTler uses the MODULE_AUTHORIZATION_TOKEN
        """
        settings_file_path = os.path.join(Authentication_Test_File_Directory, "token_module_authentication_settings.json")
        ## Create a new, temporary settings file with reference to full path to token location
        new_settings_file_path = os.path.join(Authentication_Test_File_Directory, "tmp_token_module_authentication_settings.json")
        try:
            with open(settings_file_path, 'r') as file:
                settings = json.loads(file.read())
                settings["authentication"]["token"]["module"]["file"] = os.path.join(Authentication_Test_File_Directory, settings["authentication"]["token"]["module"]["file"])
                json_settings = json.dumps(settings)

                with open(new_settings_file_path, "w") as outfile:
                    outfile.write(json_settings)
            self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py", "directed-smoke-test", settings_file=new_settings_file_path, common_settings=Common_Settings_No_Auth)
        finally:
            ## Clean up temporary settings file
            if os.path.exists(new_settings_file_path):
                os.remove(new_settings_file_path)

        experiments_dir = self.get_experiments_dir()

        ## Make sure all requests were successfully rendered.  This is because the comparisons below do not
        ## take status codes into account
        ## Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 5)
                self.assertLessEqual(total_requests_sent, 14)
                test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
                ## Validate that MODULE_AUTHORIZATION_TOKEN is used in request headers
                self.assertTrue(test_parser.validate_auth_tokens(MODULE_AUTHORIZATION_TOKEN))

        except TestFailedException:
            self.fail("Smoke test with token module auth failed")

    def test_module_with_data_auth(self):
        """ This test is equivalent to test_abc_minimal_smoke_test except we use the token module authentication mechanism
            and validate that RESTler uses the MODULE_AUTHORIZATION_TOKEN
        """
        settings_file_path = os.path.join(Authentication_Test_File_Directory, "token_module_authentication_data_settings.json")
        ## Create a new, temporary settings file with reference to full path to token location
        new_settings_file_path = os.path.join(Authentication_Test_File_Directory, "tmp_token_module_authentication_data_settings.json")
        try:
            with open(settings_file_path, 'r') as file:
                settings = json.loads(file.read())
                settings["authentication"]["token"]["module"]["file"] = os.path.join(Authentication_Test_File_Directory, settings["authentication"]["token"]["module"]["file"])
                data = str(settings["authentication"]["token"]["module"]["data"])
                json_settings = json.dumps(settings)

                with open(new_settings_file_path, "w") as outfile:
                    outfile.write(json_settings)
            self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py", "directed-smoke-test", settings_file=new_settings_file_path, common_settings=Common_Settings_No_Auth)
        finally:
            ## Clean up temporary settings file
            if os.path.exists(new_settings_file_path):
                os.remove(new_settings_file_path)

        experiments_dir = self.get_experiments_dir()

        ## Make sure all requests were successfully rendered.  This is because the comparisons below do not
        ## take status codes into account
        ## Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 5)
                self.assertLessEqual(total_requests_sent, 14)
                test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
                ## Validate that MODULE_AUTHORIZATION_TOKEN is used in request headers
                self.assertTrue(test_parser.validate_auth_tokens(MODULE_AUTHORIZATION_TOKEN))

                ## Validate that data is logged in auth log
                with open(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_AUTH), "r") as auth_log:
                    self.assertTrue(data in auth_log.read())


        except TestFailedException:
            self.fail("Smoke test with token module auth failed")


    def test_cmd_auth(self):
        """ This test is equivalent to test_abc_minimal_smoke_test except we use the token cmd authentication mechanism
            and validate that RESTler uses the CMD_AUTHORIZATION_TOKEN
        """
        settings_file_path = os.path.join(Authentication_Test_File_Directory, "token_cmd_authentication_settings.json")
        ## Create a new, temporary settings file with reference to full path to token location
        new_settings_file_path = os.path.join(Authentication_Test_File_Directory, "tmp_token_cmd_authentication_settings.json")
        try:
            with open(settings_file_path, 'r') as file:
                settings = json.loads(file.read())
                settings["authentication"]["token"]["token_refresh_cmd"] = f'python {os.path.join(Authentication_Test_File_Directory, "unit_test_server_auth.py")}'
                json_settings = json.dumps(settings)

                with open(new_settings_file_path, "w") as outfile:
                    outfile.write(json_settings)
            self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py", "directed-smoke-test", settings_file=new_settings_file_path, common_settings=Common_Settings_No_Auth)
        finally:
            ## Clean up temporary settings file
            if os.path.exists(new_settings_file_path):
                os.remove(new_settings_file_path)

        experiments_dir = self.get_experiments_dir()

        ## Make sure all requests were successfully rendered.  This is because the comparisons below do not
        ## take status codes into account
        ## Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 5)
                self.assertLessEqual(total_requests_sent, 14)
                test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
                ## Validate that CMD_AUTHORIZATION_TOKEN is used in request headers
                self.assertTrue(test_parser.validate_auth_tokens(CMD_AUTHORIZATION_TOKEN))

        except TestFailedException:
            self.fail("Smoke test with token cmd auth failed")


    def test_abc_invalid_b_smoke_test(self):
        self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar_invalid_b.py", "directed-smoke-test", settings_file="test_one_schema_settings.json")
        experiments_dir = self.get_experiments_dir()

        # Make sure all requests were successfully rendered.  This is because the comparisons below do not
        # take status codes into account
        # Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 1)
                self.assertLessEqual(total_requests_sent, 2)

            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "abc_smoke_test_invalid_b_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Smoke test failed: Fuzzing")

    def test_abc_minimal_smoke_test(self):
        """ This checks that the directed smoke test executes the expected
        sequences in Test mode, without generating extra sequences, for a simple
        example.  Let 5 requests A, B, C, D, E where:
        - A and B have no pre-requisites
        - C and D both depend on A and B (they are identical)
        - E depends on D

        In the current implementation, all sequences for A, B, C, D will be
        rendered "from scratch", but the sequence for E will reuse the 'D' prefix.

        """
        self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py", "directed-smoke-test")
        experiments_dir = self.get_experiments_dir()

        # Make sure all requests were successfully rendered.  This is because the comparisons below do not
        # take status codes into account

        # Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 5)
                self.assertLessEqual(total_requests_sent, 14)

            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "abc_smoke_test_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Smoke test failed: Fuzzing")


    def test_abc_minimal_smoke_test_prefix_cache(self):
        """ This checks that the directed smoke test executes the expected
        sequences in Test mode with test-all-combinations and when caching prefix sequences for several
        request types via the engine settings.

        Let 5 requests A, B, C, D, E where:
        - A and B have no pre-requisites
        - C and D both depend on A and B (they are identical)
        - E depends on D

        In the current implementation, all sequences for A, B, C, D will be
        rendered "from scratch", but the sequence for E will reuse the 'D' prefix (as confirmed by a separate test above).

        This test introduces 2 combinations for C, D, and E, and confirms that for the second combination,
        no requests are re-rendered for C and D (GET requests), but the combination is re-rendered for the PUT
        (as specified in the settings file).


        """
        self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar_combinations.py", "test-all-combinations",
                                settings_file="test_one_schema_settings.json")
        experiments_dir = self.get_experiments_dir()

        ## Make sure all requests were successfully rendered.  This is because the comparisons below do not
        ## take status codes into account

        ## Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 5)
                self.assertLessEqual(total_requests_sent, 22)

            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "abc_smoke_test_testing_log_all_combinations.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Smoke test failed: Fuzzing")

        # Now run the same test with the additional settings file.
        self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar_combinations.py", "test-all-combinations",
                                settings_file="abc_smoke_test_settings_prefix_cache.json")
        experiments_dir = self.get_experiments_dir()
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")
        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 5)
                self.assertLessEqual(total_requests_sent, 20)

        except TestFailedException:
            self.fail("Smoke test failed: Fuzzing")


    def test_ab_all_combinations_with_sequence_failure(self):
        """ This checks that sequence failures are correctly reported in the
        spec coverage file for a minimal grammar.
        Let 2 requests A, B where:
        - B depends on A
        - There are 2 renderings of B, and 2 renderings of A, so four sequences AB
        will be tested.
        - A is flaky - it returns '200' on odd invocations, and '400' on even invocations.

        The spec coverage file should contain:
            - 2 entries for A, one valid and one invalid
            - 2 entries for B, one valid and one 'sequence_failure' entry, with a
               sample request for the failed execution of A

        The test checks that the sequence failure sample requests are correct.
        """
        self.run_abc_smoke_test(Test_File_Directory, "ab_flaky_b_grammar.py", "test-all-combinations", settings_file="always_render_full_seq_settings.json")
        experiments_dir = self.get_experiments_dir()

        # Make sure all requests were successfully rendered.  This is because the comparisons below do not
        # take status codes into account

        # Make sure the right number of requests was sent.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 2)
                self.assertLessEqual(total_requests_sent, 6)

            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "ab_flaky_b_all_combinations_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))

            baseline_speccov_json_file_path = os.path.join(Test_File_Directory, "ab_flaky_b_all_combinations_speccov.json")
            test_speccov_json_file_path = os.path.join(experiments_dir, "logs", "speccov.json")
            # The speccov files should be identical
            with open(baseline_speccov_json_file_path, 'r') as file1:
                with open(test_speccov_json_file_path, 'r') as file2:
                    baseline_json = json.loads(file1.read())
                    test_json = json.loads(file2.read())
                    # Remove the timestamps
                    for spec in [baseline_json, test_json]:
                        for key, val in spec.items():
                            if 'sequence_failure_sample_request' in val:
                                val['sequence_failure_sample_request']['response_received_timestamp'] = None
                            if 'sample_request' in val:
                                val['sample_request']['response_received_timestamp'] = None
                    self.assertTrue(baseline_json == test_json)

        except TestFailedException:
            self.fail("Smoke test failed: Fuzzing")

    def test_abc_input_dependencies_smoke_test(self):
        """ This checks that the directed smoke test executes the expected
        sequences in Test mode, when one of the dependencies is not returned in the
        response but instead is specified in a uuid4_suffix in the request primitive.

        """
        self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar_without_responses.py", "directed-smoke-test")
        experiments_dir = self.get_experiments_dir()

        # Make sure the right number of requests was sent and rendered successfully.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                num_fully_valid = testing_summary["num_fully_valid"]
                self.assertEqual(num_fully_valid, 3)
                self.assertLessEqual(total_requests_sent, 5)

            # Check that the body of the GET request contains the return value from the PUT request, and that
            # it is a uuid suffix.
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            get_request = test_parser._seq_list[-1].requests[-1]
            self.assertTrue(get_request.method == 'GET')
            # The below length of the body indicates that a uuid_suffix value was inserted
            self.assertTrue(len(get_request.body) == 30)
        except TestFailedException:
            self.fail("Smoke test failed: Test mode.")

    def test_dynamic_obj_writer_in_primitives(self):
        """ This checks that a dynamic object writer is correctly used for every supported primitive type.

        The structure of the test is as follows:

        - 'test_dynamic_obj_writer.py' is a grammar that contains a PUT request for /city/{cityName},
           and a GET request for /city/{cityName}.
        - The test loops over all the primitives to test, and replaces the line in the grammar that
          specifies the value of the 'cityName' path parameter.  For example,
                restler_custom_payload_uuid4_suffix("cityName", writer=x.writer()) ->
                restler_fuzzable_string("my_cityName", writer=x.writer())
        - For each primitive, test runs the RESTler smoke test and confirms that:
           1. All of the requests succeeded (this confirms that the dynamc object was assigned and used in the GET.
           2. The expected value was used in the path of the GET request (this can be confirmed using speccov.json)

        """

        # First, test the basic setup is working
        test_file_dir = Test_File_Directory
        fuzzing_mode = "directed-smoke-test"
        grammar_file_name = "test_dynamic_obj_writer.py"
        grammar_file_path = os.path.join(test_file_dir, grammar_file_name)
        new_grammar_file_path = os.path.join(test_file_dir, f"temp_{grammar_file_name}")

        test_strings = [
            # custom payloads
            "\tprimitives.restler_custom_payload(\"cityName\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_custom_payload_header(\"cityName\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_custom_payload_query(\"cityName\", writer=_city_put_name.writer()),\n",
            ## fuzzable payloads
            "\tprimitives.restler_fuzzable_string(\"Seattle\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_bool(\"Seattle\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_date(\"Seattle\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_datetime(\"Seattle\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_int(\"Seattle\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_number(\"Seattle\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_object(\"Seattle\", writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_group(\"enum_name\", [\"Seattle\"], writer=_city_put_name.writer()),\n",
            "\tprimitives.restler_fuzzable_uuid4(\"Seattle\", writer=_city_put_name.writer()),\n",
        ]

        for test_string in test_strings:
            with open(grammar_file_path, 'r') as grammar_file:
                with open(new_grammar_file_path, 'w') as new_grammar_file:
                    grammar_lines = grammar_file.readlines()
                    grammar_lines[22] = test_string
                    new_grammar_file.writelines(grammar_lines)
            dict_file_path = os.path.join(test_file_dir, "dynamic_obj_dict.json")
            args = Common_Settings + [
            '--fuzzing_mode', f"{fuzzing_mode}",
            '--restler_grammar', f'{new_grammar_file_path}',
            '--custom_mutations', f'{dict_file_path}'
            ]

            self.run_restler_engine(args)
            experiments_dir = self.get_experiments_dir()

            testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

            try:
                with open(testing_summary_file_path, 'r') as file:
                    testing_summary = json.loads(file.read())
                    total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                    num_fully_valid = testing_summary["num_fully_valid"]
                    self.assertEqual(num_fully_valid, 2, test_string)
                    self.assertEqual(total_requests_sent, 3)

                test_network_logs = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
                # There are two test cases (sequences) expected, one for each request.
                tested_requests = test_network_logs._seq_list[1].requests

                self.assertEqual(len(tested_requests), 2)
                # The custom payload value is 'Seattle'.
                if 'restler_fuzzable_uuid4' not in test_string:
                    self.assertTrue('Seattle' in tested_requests[1].endpoint)

            except TestFailedException:
                self.fail("Smoke test failed: Fuzzing")
            finally:
                if os.path.exists(experiments_dir):
                    shutil.rmtree(experiments_dir)
                if os.path.exists(new_grammar_file_path):
                    os.remove(new_grammar_file_path)


    def test_smoke_test(self):
        """ This checks that the directed smoke test executes all
        of the expected requests in the correct order with correct
        arguments from the dictionary.
        """
        args = Common_Settings + [
        '--fuzzing_mode', 'directed-smoke-test',
        '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar.py")}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "smoke_test_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Smoke test failed: Fuzzing")

        try:
            default_parser = GarbageCollectorLogParser(os.path.join(Test_File_Directory, "smoke_test_gc_log.txt"))
            test_parser = GarbageCollectorLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_GC))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Smoke test failed: Garbage Collector")

        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                total_gc_requests_sent = testing_summary["total_requests_sent"]["gc"]
                total_object_creations = testing_summary["total_object_creations"]
                self.assertLessEqual(total_requests_sent, 75)
                self.assertLessEqual(total_object_creations, 50)
                self.assertEqual(total_gc_requests_sent, 34)
        except TestFailedException:
            self.fail("Smoke test failed: testing summary.")


    def test_create_once(self):
        """ This checks that a directed smoke test, using create once endpoints,
        executes all of the expected requests in the correct order with correct
        arguments from the dictionary.
        """
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--settings', f'{os.path.join(Test_File_Directory, "test_settings_createonce.json")}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode} {result.stdout}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "create_once_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Create-once failed: Fuzzing")

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "create_once_pre_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_PREPROCESSING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Create-once failed: Preprocessing")

        try:
            default_parser = GarbageCollectorLogParser(os.path.join(Test_File_Directory, "create_once_gc_log.txt"))
            test_parser = GarbageCollectorLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_GC))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Create-once failed: Garbage Collector")

    def test_checkers(self):
        """ This checks that a directed smoke test, with checkers enabled,
        bugs planted for each checker, and a main driver bug, will produce the
        appropriate bug buckets and the requests will be sent in the correct order.
        """
        def test(settings_file_name):
            settings_file_path = os.path.join(Test_File_Directory, settings_file_name)

            args = Common_Settings + [
                '--fuzzing_mode', 'directed-smoke-test',
                '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar_bugs.py")}',
                '--enable_checkers', '*',
                '--disable_checkers', 'invalidvalue',
                '--settings', f'{settings_file_path}'
            ]

            result = subprocess.run(args, capture_output=True)
            if result.stderr:
                self.fail(result.stderr)
            try:
                result.check_returncode()
            except subprocess.CalledProcessError:
                self.fail(f"Restler returned non-zero exit code: {result.returncode} {result.stdout}")

            experiments_dir = self.get_experiments_dir()

            try:
                default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "checkers_testing_log.txt"))
                test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
                self.assertTrue(default_parser.diff_log(test_parser))
            except TestFailedException:
                self.fail("Checkers failed: Fuzzing")

            try:
                default_parser = BugLogParser(os.path.join(Test_File_Directory, "checkers_bug_buckets.txt"))
                test_parser = BugLogParser(os.path.join(experiments_dir, 'bug_buckets', 'bug_buckets.txt'))
                self.assertTrue(default_parser.diff_log(test_parser))
            except TestFailedException:
                self.fail("Checkers failed: Bug Buckets")

            try:
                default_parser = GarbageCollectorLogParser(os.path.join(Test_File_Directory, "checkers_gc_log.txt"))
                test_parser = GarbageCollectorLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_GC))
                self.assertTrue(default_parser.diff_log(test_parser))
            except TestFailedException:
                self.fail("Checkers failed: Garbage Collector")

            try:
                testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

                with open(testing_summary_file_path, 'r') as file:
                    testing_summary = json.loads(file.read())
                    total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                    total_gc_requests_sent = testing_summary["total_requests_sent"]["gc"]
                    total_object_creations = testing_summary["total_object_creations"]
                    self.assertLessEqual(total_requests_sent, 40)
                    self.assertLessEqual(total_object_creations, 102)
                    self.assertEqual(total_gc_requests_sent, 51)
            except TestFailedException:
                self.fail("Smoke test failed: testing summary.")

        settings_files = [
            "test_one_schema_settings.json",
            "test_gc_during_main_loop_settings.json"
        ]
        for settings_file_name in settings_files:
            test(settings_file_name)

    def test_multi_dict(self):
        """ This checks that the directed smoke test executes all of the expected
        requests in the correct order when a second dictionary is specified in the
        settings file to be used for one of the endpoints.
        """
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--settings', f'{os.path.join(Test_File_Directory, "test_settings_multidict.json")}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "multidict_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Multi-dict failed: Fuzzing")

        try:
            default_parser = GarbageCollectorLogParser(os.path.join(Test_File_Directory, "multidict_gc_log.txt"))
            test_parser = GarbageCollectorLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_GC))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Multi-dict failed: Garbage Collector")

    def test_fuzz(self):
        """ This checks that a bfs-cheap fuzzing run executes all of the expected
        requests in the correct order with correct arguments from the dictionary.
        The test runs for 3 minutes and checks 100 sequences
        """
        Fuzz_Time = 0.1 # 6 minutes
        Num_Sequences = 300
        settings_file_path = os.path.join(Test_File_Directory, "test_fuzz_settings.json")

        args = Common_Settings + [
            '--fuzzing_mode', 'bfs-cheap',
            '--restler_grammar',f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--time_budget', f'{Fuzz_Time}',
            '--enable_checkers', '*',
            '--disable_checkers', 'namespacerule', 'invalidvalue',
            '--settings', f'{settings_file_path}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(f"{result.stderr}")
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode}, Stdout: {result.stdout}")

        experiments_dir = self.get_experiments_dir()
        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "fuzz_testing_log.txt"), max_seq=Num_Sequences)
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING), max_seq=Num_Sequences)
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Fuzz failed: Fuzzing")

    def test_payload_body_checker(self):
        """ This checks that the payload body checker sends all of the correct
        requests in the correct order and an expected 500 bug is logged. The test
        sends requests in a predictable order and will test invalid json, type changes,
        and structure changes using DROP and SELECT algorithms.

        If this test fails it is important to verify (by diffing the current baseline files)
        that the differences that caused the failure are expected by a recent change and no other
        unexpected changes exist.

        """

        settings_file_path = os.path.join(Test_File_Directory, "test_one_schema_settings.json")

        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--enable_checkers', 'payloadbody',
            '--settings', f'{settings_file_path}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode} {result.stdout}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "payloadbody_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
        except TestFailedException:
            self.fail("Payload body failed: Fuzzing")

        try:
            default_parser = BugLogParser(os.path.join(Test_File_Directory, "payloadbody_bug_buckets.txt"))
            test_parser = BugLogParser(os.path.join(experiments_dir, 'bug_buckets', 'bug_buckets.txt'))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Payload body failed: Bug Buckets")

        try:
            default_parser = GarbageCollectorLogParser(os.path.join(Test_File_Directory, "payloadbody_gc_log.txt"))
            test_parser = GarbageCollectorLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_GC))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Payload body failed: Garbage Collector")

    def test_payload_body_checker_advanced(self):
        """ This checks that the payload body checker sends all of the correct
        requests in the correct order for more complicated bodies.
        The bodies in this test include arrays and nested dict objects. The test
        sends requests in a predictable order and will test invalid json, type changes,
        and structure changes using DROP and SELECT algorithms.

        If this test fails it is important to verify (by diffing the current baseline file)
        that the differences that caused the failure are expected by a recent change and no other
        unexpected changes exist.

        """
        settings_file_path = os.path.join(Test_File_Directory, "test_one_schema_settings.json")
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar_body.py")}',
            '--enable_checkers', 'payloadbody',
            '--settings', f'{settings_file_path}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "payloadbody_advanced_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
        except TestFailedException:
            self.fail("Payload body arrays failed: Fuzzing")

    def test_invalid_value_checker(self):
        """ This checks that the invalid value checker sends all of the correct
        requests in the correct order and an expected 500 bug is logged.
        The test specifies a random seed to the checker, so the logs are expected
        to be identical on every run.

        If this test fails it is important to verify (by diffing the current baseline files)
        that the differences that caused the failure are expected by a recent change and no other
        unexpected changes exist.

        """

        settings_file_path = os.path.join(Test_File_Directory, "test_invalid_value_checker_settings.json")

        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--enable_checkers', 'invalidvalue',
            '--settings', f'{settings_file_path}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode} {result.stdout}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "invalidvalue_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Invalid value checker failed: Fuzzing")

        try:
            default_parser = BugLogParser(os.path.join(Test_File_Directory, "invalidvalue_bug_buckets.txt"))
            test_parser = BugLogParser(os.path.join(experiments_dir, 'bug_buckets', 'bug_buckets.txt'))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Invalid value checker failed: Bug Buckets")

        try:
            default_parser = GarbageCollectorLogParser(os.path.join(Test_File_Directory, "invalidvalue_gc_log.txt"))
            test_parser = GarbageCollectorLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_GC))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Invalid value checker failed: Garbage Collector")

    def test_invalid_value_checker_advanced(self):
        """ This checks that the invalid value checker sends all of the correct
        requests in the correct order for more complicated bodies.
        The bodies in this test include arrays and nested dict objects.  The test specifies a random seed
        to the checker, so the logs are expected to be identical on every run.

        If this test fails it is important to verify (by diffing the current baseline file)
        that the differences that caused the failure are expected by a recent change and no other
        unexpected changes exist.

        """
        settings_file_path = os.path.join(Test_File_Directory, "test_invalid_value_checker_settings.json")
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar_body.py")}',
            '--enable_checkers', 'invalidvalue',
            '--settings', f'{settings_file_path}'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "invalidvalue_advanced_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Invalid value advanced failed: Fuzzing")

        try:
            default_parser = BugLogParser(os.path.join(Test_File_Directory, "invalidvalue_advanced_bug_buckets.txt"))
            test_parser = BugLogParser(os.path.join(experiments_dir, 'bug_buckets', 'bug_buckets.txt'))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Invalid value advanced failed: Bug Buckets")

    def test_examples_checker(self):
        """ This checks that the examples checker sends the correct requests
        in the correct order when query or body examples are present
        """
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--enable_checkers', 'examples'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode} {result.stdout}")

        experiments_dir = self.get_experiments_dir()

        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "examples_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
        except TestFailedException:
            self.fail("Payload body failed: Fuzzing")

        try:
            default_parser = GarbageCollectorLogParser(os.path.join(Test_File_Directory, "examples_gc_log.txt"))
            test_parser = GarbageCollectorLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_GC))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Payload body failed: Garbage Collector")

    def test_value_generators(self):
        """ This test checks that dynamic value generation works as expected for one use case, which is
        expected to be typical: a request has some values that are statically generated, and some that are
        dynamically generated.  Other tests that test the fine-grained behavior of value generation are
        covered in 'test_value_generators.py'.
        """
        # Read the settings file and modify the path to be an absolute path
        value_generator_file_name = "custom_value_gen.py"
        settings_file_name = "value_gen_settings.json"
        settings_file_path = os.path.join(Test_File_Directory, settings_file_name)
        settings = json.load(open(settings_file_path, encoding='utf-8'))
        settings["custom_value_generators"] = os.path.join(Test_File_Directory, value_generator_file_name)
        json.dump(settings, open(settings_file_path, "w", encoding='utf-8'))
        self.run_abc_smoke_test(Test_File_Directory, "value_gen_test_grammar.py", "test-all-combinations",
                                settings_file="value_gen_settings.json",
                                dictionary_file_name="value_gen_dict.json")

        experiments_dir = self.get_experiments_dir()

        # Make sure the expected number of requests was sent, and the logs match.
        # Note: all of the Gen-2 requests are expected to fail,
        # since the grammar contains requests that are not implemented in
        # the test server.  The responses from the server are not important for this test.
        testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")

        try:
            with open(testing_summary_file_path, 'r') as file:
                testing_summary = json.loads(file.read())
                total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                total_object_creations = testing_summary["total_object_creations"]
                self.assertLessEqual(total_requests_sent, 78)  # 6 gen1 + 6 [gen1] * (2 * 6) gen2
                self.assertLessEqual(total_object_creations, 42)

            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "value_gen_testing_log.txt"))
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
            self.assertTrue(default_parser.diff_log(test_parser))
        except TestFailedException:
            self.fail("Smoke test failed: Fuzzing")

    def test_logger_jsonformatted_bugbuckets(self):

        def verify_bug_details(baseline_bugdetail_filename, actual_bugdetail_filename):
            try:
            #Verify the generated bug details in json format.
                default_parser = JsonFormattedBugsLogParser(baseline_bugdetail_filename, JsonFormattedBugsLogParser.FileType.BugDetails)
                test_parser = JsonFormattedBugsLogParser(actual_bugdetail_filename, JsonFormattedBugsLogParser.FileType.BugDetails)
                self.assertTrue(default_parser._bug_detail['status_code'] == test_parser._bug_detail['status_code'])
                self.assertTrue(default_parser._bug_detail['checker_name'] == test_parser._bug_detail['checker_name'])
                self.assertTrue(default_parser._bug_detail['reproducible'] == test_parser._bug_detail['reproducible'])
                self.assertTrue(default_parser._bug_detail['verb'] == test_parser._bug_detail['verb'])
                self.assertTrue(default_parser._bug_detail['endpoint'] == test_parser._bug_detail['endpoint'])
                self.assertTrue(default_parser._bug_detail['status_text'] == test_parser._bug_detail['status_text'])
                self.assertTrue(len(default_parser._bug_detail['request_sequence']) == len(test_parser._bug_detail['request_sequence']))
            except TestFailedException:
                self.fail("verification of bugs details file failed")


        settings_file_path = os.path.join(Test_File_Directory, "test_one_schema_settings.json")
        args = Common_Settings + [
                '--fuzzing_mode', 'directed-smoke-test',
                '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar_bugs.py")}',
                '--enable_checkers', '*',
                '--disable_checkers', 'invalidvalue',
                '--settings', f'{settings_file_path}'
            ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode}")

        experiments_dir = self.get_experiments_dir()
        try:
            #Verify the generated bugs.json file
            default_parser = JsonFormattedBugsLogParser(os.path.join(Test_File_Directory, "Bug_Buckets_Json","Bugs_Bucket_AsJson.json"),
                                                        JsonFormattedBugsLogParser.FileType.Bugs)
            test_parser = JsonFormattedBugsLogParser(os.path.join(experiments_dir, 'bug_buckets', 'Bugs.json'),
                                                     JsonFormattedBugsLogParser.FileType.Bugs)
            self.assertTrue(len(default_parser._bug_list) == len(test_parser._bug_list), "Expected count of bugs are not same.")
            counter = 0
            for expected_bug in default_parser._bug_list:
                actual_bug = test_parser._bug_list[counter]
                self.assertTrue(expected_bug == actual_bug ,f"Expected bug :{expected_bug} and actual bug :{actual_bug} are different")
                counter = counter + 1
        except TestFailedException:
            self.fail("verification of bugs json file failed")

        verify_bug_details(os.path.join(Test_File_Directory,"Bug_Buckets_Json", "InvalidDynamicObjectChecker_20x_1.json"),
                           os.path.join(experiments_dir, 'bug_buckets', 'InvalidDynamicObjectChecker_20x_1.json'))

        verify_bug_details(os.path.join(Test_File_Directory,"Bug_Buckets_Json", "UseAfterFreeChecker_20x_1.json"),
                           os.path.join(experiments_dir, 'bug_buckets', 'UseAfterFreeChecker_20x_1.json'))


    def test_gc_limits(self):
        """ This test checks that RESTler exits after N objects cannot be deleted according
        to the settings.  It also tests that async resource deletion is being performed.
        """
        def run_test(max_objects, run_gc_after_every_test):
            settings_file_name = "gc_test_settings.json"
            temp_settings_file_name = "tmp_gc_test_settings.json"
            try:
                settings_file_path = os.path.join(Test_File_Directory, settings_file_name)
                temp_settings_file_path = os.path.join(Test_File_Directory, temp_settings_file_name)
                settings = json.load(open(settings_file_path, encoding='utf-8'))
                settings["garbage_collector_cleanup_time"] = 20
                if max_objects:
                    settings["max_objects_per_resource_type"] = max_objects
                json.dump(settings, open(temp_settings_file_path, "w", encoding='utf-8'))
                self.run_abc_smoke_test(Test_File_Directory, "gc_test_grammar.py", "test-all-combinations",
                                        settings_file=temp_settings_file_name,
                                        dictionary_file_name="gc_test_dict.json",
                                        failure_expected=True)
            finally:
                if os.path.exists(temp_settings_file_name):
                    os.remove(temp_settings_file_name)

        def check_gc_error(max_objects):
            experiments_dir = self.get_experiments_dir()

            # Expected: Exception during garbage collection: Limit exceeded for objects of type _post_large_resource (4 > 3).
            gc_file_path = glob.glob(os.path.join(experiments_dir, 'logs', f'garbage_collector.gc.*.1.txt'))[0]
            with open(gc_file_path) as file:
                gc_log = file.readlines()
                expected_has_error = max_objects is not None
                actual_has_error = "Limit exceeded for objects of type _post_large_resource (4 > 3)" in gc_log[-1]
                self.assertEqual(expected_has_error, actual_has_error)


        def check_gc_stats(max_objects):
            experiments_dir = self.get_experiments_dir()

            gc_stats_file_path = os.path.join(experiments_dir, "logs", "gc_summary.json")
            with open(gc_stats_file_path) as file:
                gc_log = json.loads(file.read())
                if max_objects is None:
                    # 7 objects are expected to be created in Gen-1 and Gen-2.
                    # 5 of these are successful (per test server implementation), and the rest exit with 409
                    successful_creates = 5 * 2
                    self.assertGreaterEqual(gc_log["delete_stats"]["_post_large_resource"]["202"], successful_creates)
                    self.assertGreaterEqual(gc_log["delete_stats"]["_post_large_resource"]["409"], 14 - successful_creates)
                else:
                    successful_creates = max_objects * 2
                    self.assertGreaterEqual(gc_log["delete_stats"]["_post_large_resource"]["202"], successful_creates)
                    self.assertGreaterEqual(gc_log["delete_stats"]["_post_large_resource"]["409"], 14 - successful_creates)

        run_test(3, True)
        check_gc_error(3)
        check_gc_stats(3)

        run_test(3, False)
        check_gc_error(3)
        check_gc_stats(3)

        run_test(None, False)
        check_gc_error(None)
        check_gc_stats(None)

    def test_random_seed_settings(self):
        """ This test is identical to test_abc_minimal_smoke_test, except that it modifies the random seed
        settings.  The test checks that the same sequences are sent in 'test' mode, but different sequences
        are sent in 'random-walk' mode, and tests that the seed was output to the testing summary.
        """
        def create_settings_file(settings):
            new_settings_file_path = os.path.join(Test_File_Directory, "random_seed_settings.json")
            try:
                json_settings = json.dumps(settings, indent=4)
                with open(new_settings_file_path, "w") as f:
                    f.write(json_settings)
                return new_settings_file_path
            except Exception as e:
                print(e)
                return None

        def test_with_settings(settings):
            try:
                new_settings_file_path = create_settings_file(settings)
                self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py",
                                        "directed-smoke-test", settings_file=new_settings_file_path)
            finally:
                ## Clean up temporary settings file
                if os.path.exists(new_settings_file_path):
                    os.remove(new_settings_file_path)

            experiments_dir = self.get_experiments_dir()

            # Make sure all requests were successfully rendered.  This is because the comparisons below do not
            # take status codes into account

            # Make sure the right number of requests was sent.
            testing_summary_file_path = os.path.join(experiments_dir, "logs", "testing_summary.json")
            DEFAULT_RANDOM_SEED = 12345
            try:
                with open(testing_summary_file_path, 'r') as file:
                    testing_summary = json.loads(file.read())
                    total_requests_sent = testing_summary["total_requests_sent"]["main_driver"]
                    num_fully_valid = testing_summary["num_fully_valid"]
                    self.assertEqual(num_fully_valid, 5)
                    self.assertLessEqual(total_requests_sent, 14)

                    # Make sure the random seed was output to the testing summary
                    if 'random_seed' in settings:
                        if 'generate_random_seed' in settings:
                            self.assertNotEqual(testing_summary["settings"]["random_seed"], settings["random_seed"])
                        else:
                            self.assertEqual(testing_summary["settings"]["random_seed"], settings["random_seed"])
                    else:
                        if 'generate_random_seed' in settings:
                            self.assertNotEqual(testing_summary["settings"]["random_seed"], DEFAULT_RANDOM_SEED)
                        else:
                            self.assertEqual(testing_summary["settings"]["random_seed"], DEFAULT_RANDOM_SEED)

                default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "abc_smoke_test_testing_log.txt"))
                test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING))
                self.assertTrue(default_parser.diff_log(test_parser))
            except TestFailedException:
                self.fail("Smoke test failed: Fuzzing")

        def random_walk_test(settings, expected_equal):

            try:
                new_settings_file_path = create_settings_file(settings)
                # First run
                self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py",
                                        "random-walk", settings_file=new_settings_file_path)
                experiments_dir = self.get_experiments_dir()

                parser_1 = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING), max_seq=20)

                # Second run
                self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar.py",
                                        "random-walk", settings_file=new_settings_file_path)
                experiments_dir = self.get_experiments_dir()

                parser_2 = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING), max_seq=20)
                diff_result = parser_1.diff_log(parser_2)
                if expected_equal:
                    self.assertTrue(diff_result)
                else:
                    self.assertFalse(diff_result)

            finally:
                ## Clean up temporary settings file
                if os.path.exists(new_settings_file_path):
                    os.remove(new_settings_file_path)

        # Test with a random seed
        test_with_settings({"random_seed": 1234})

        # Test with a random seed and generate_random_seed
        test_with_settings({"random_seed": 1234, "generate_random_seed": True})

        # Test with no random seed
        test_with_settings({})

        # Test with generate_random_seed
        test_with_settings({"generate_random_seed": True})

        # Test two runs without a random seed specified.  The same random seed should be used,
        # and the payloads are expected to be equal.
        random_walk_test({ "time_budget": 0.01}, True)

        # Test two runs with 'generate_random_seed' set to True.  Different random seeds should be used,
        # and the payloads are expected to be different.
        random_walk_test({"generate_random_seed": True, "time_budget": 0.01}, False)

    def test_trace_database_minimal(self):
        """ This test invokes the abc_smoke_test with the setting to produce a trace database enabled,
        then checks the database against a checked-in baseline.  Both databases are deserialized, and the
        contents are compared, excluding timestamps and ids.

        Because this test uses the 'ABC' smoke test, it does not invoke the GC and only the invalid
        dynamic object checker is applicable.  The main purpose of this test is to have a short sanity run
        with a small baseline that can be manually inspected.
        """

        def run_trace_db_test(custom_serializer_file_name=None, checkers=None, grammar_file_name="abc_test_grammar.py",
                              dictionary_file_name=None):

            new_settings_file_path = os.path.join(Test_File_Directory, f"tmp_trace_db_settings.json")
            if os.path.exists(new_settings_file_path):
                os.remove(new_settings_file_path)
            settings = {}
            settings["trace_database"] = {}
            settings["include_unique_sequence_id"] = False
            settings["use_trace_database"] = True
            trace_db_path = None
            if custom_serializer_file_name is not None:
                custom_serializer_module_file_path = os.path.join(Test_File_Directory, custom_serializer_file_name)
                custom_serializer_settings = {}
                custom_serializer_settings["module_file_path"] = custom_serializer_module_file_path
                # Using the text serializer
                trace_db_path = os.path.join(os.getcwd(), "trace_data.txt")
                custom_serializer_settings["log_file"] = trace_db_path
                settings["trace_database"]["custom_serializer"] = custom_serializer_settings
            else:
                # default serializer .ndjson file
                trace_db_file_name = "trace_data.ndjson"

            with open(new_settings_file_path, "w") as outfile:
                outfile.write(json.dumps(settings, indent=4))

            self.run_abc_smoke_test(Test_File_Directory, grammar_file_name,
                                    "directed-smoke-test",
                                    dictionary_file_name=dictionary_file_name,
                                    settings_file=new_settings_file_path,
                                    enable_checkers=checkers)

            if trace_db_path is None:
                trace_db_path = os.path.join(self.get_experiments_dir(), "trace_data.ndjson")

            if not os.path.exists(trace_db_path):
                self.fail("Trace DB file not found")

            if custom_serializer_file_name is None:
                if checkers is None:
                    baseline_trace_db_path = os.path.join(Test_File_Directory, "trace_data_baseline.ndjson")
                else:
                    baseline_trace_db_path = os.path.join(Test_File_Directory, "trace_data_baseline_checkers.ndjson")

                print(f"Comparing trace DB to baseline: {baseline_trace_db_path}")

                baseline_deserializer = trace_db.JsonTraceLogReader(log_file_paths=[baseline_trace_db_path])
                actual_deserializer = trace_db.JsonTraceLogReader(log_file_paths=[trace_db_path])

                baseline_trace_messages = baseline_deserializer.load()
                actual_trace_messages = actual_deserializer.load()

                normalized_baseline = [log.normalize() for log in baseline_trace_messages]
                normalized_actual = [log.normalize() for log in actual_trace_messages]
                if len(normalized_baseline) != len(normalized_actual):
                    message = f"baseline log count {len(normalized_baseline)} != actual log count {len(normalized_actual)}"
                    self.fail(f"Trace DBs do not match: {message}")
                for i, x in enumerate(normalized_baseline):
                    y = normalized_actual[i]
                    if x != y:
                        message = f"different baseline log \n{json.dumps(x.to_dict(), indent=4)} \nto actual log \n{json.dumps(y.to_dict(), indent=4)}"
                        self.fail(f"Trace DBs do not match: {message}")

                # TODO: test that all requests have an origin and that the counts match the
                # counts in the testing summary
                #
            else:
                baseline_trace_db_path = os.path.join(Test_File_Directory, "abc_smoke_test_trace_data_baseline.txt")
                print(f"Comparing trace DB to baseline: {baseline_trace_db_path}")
                # Import the TraceDbTextReader
                trace_db_text_reader =  import_utilities.import_subclass(custom_serializer_module_file_path,
                                                                         TraceLogReaderBase)

                baseline_deserializer = trace_db_text_reader(baseline_trace_db_path)
                actual_deserializer = trace_db_text_reader(trace_db_path)

                baseline_trace_messages = baseline_deserializer.load()
                actual_trace_messages = actual_deserializer.load()

                for i, x in enumerate(baseline_trace_messages):
                    y = actual_trace_messages[i]
                    if x != y:
                        print(f"different baseline log {x} to actual log {y}")
                        self.fail("Trace DBs do not match")
            print("passed")

        # Run the test with a default serializer
        run_trace_db_test()

        # Run the test with a custom serializer
        custom_serializer_file_name = "trace_db_text_serializer.py"
        run_trace_db_test(custom_serializer_file_name)

        # Run the test with checkers and GC
        # The ABC smoke test does not have any GCed objects, so use the 'test_grammar.py'
        checkers = [
            'invaliddynamicobject', # The ABC smoketest does not have any parameters except dynamic objects
        ]
        run_trace_db_test(checkers=",".join(checkers))
