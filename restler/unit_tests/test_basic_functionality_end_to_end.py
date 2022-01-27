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
import sys
import shutil
import subprocess
import json
import utils.logger as logger
from collections import namedtuple

from test_servers.log_parser import *

Test_File_Directory = os.path.join(
    os.path.dirname(__file__), 'log_baseline_test_files'
)

Restler_Path = os.path.join(os.path.dirname(__file__), '..', 'restler.py')

Common_Settings = [
    "python", "-B", Restler_Path, "--use_test_socket",
    '--custom_mutations', f'{os.path.join(Test_File_Directory, "test_dict.json")}',
    "--garbage_collection_interval", "30", "--host", "unittest",
    "--token_refresh_cmd", f'python {os.path.join(Test_File_Directory, "unit_test_server_auth.py")}',
    "--token_refresh_interval", "10"
]

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

    def run_restler_engine(self, args):
        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(result.stderr)
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode} {result.stdout}")

    def run_abc_smoke_test(self, test_file_dir, grammar_file_name, fuzzing_mode):
        grammar_file_path = os.path.join(test_file_dir, grammar_file_name)
        dict_file_path = os.path.join(test_file_dir, "abc_dict.json")
        args = Common_Settings + [
        '--fuzzing_mode', f"{fuzzing_mode}",
        '--restler_grammar', f'{grammar_file_path}',
        '--custom_mutations', f'{dict_file_path}'
        ]
        self.run_restler_engine(args)

    def tearDown(self):
        try:
            shutil.rmtree(self.get_experiments_dir())
        except Exception as err:
            print(f"tearDown function failed: {err!s}.\n"
                  "Experiments directory was not deleted.")

    def test_abc_invalid_b_smoke_test(self):
        self.run_abc_smoke_test(Test_File_Directory, "abc_test_grammar_invalid_b.py", "directed-smoke-test")
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
        self.run_abc_smoke_test(Test_File_Directory, "ab_flaky_b_grammar.py", "test-all-combinations")
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
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar_bugs.py")}',
            '--enable_checkers', '*'
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
        args = Common_Settings + [
            '--fuzzing_mode', 'bfs-cheap',
            '--restler_grammar',f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--time_budget', f'{Fuzz_Time}',
            '--enable_checkers', '*',
            '--disable_checkers', 'namespacerule'
        ]

        result = subprocess.run(args, capture_output=True)
        if result.stderr:
            self.fail(f"{result.stderr}")
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            self.fail(f"Restler returned non-zero exit code: {result.returncode}, Stdout: {result.stdout}")

        experiments_dir = self.get_experiments_dir()
        #experiments_dir = "D:\git\restler-fuzzer\restler\RestlerResults\experiment31916"
        try:
            default_parser = FuzzingLogParser(os.path.join(Test_File_Directory, "fuzz_testing_log.txt"), max_seq=Num_Sequences)
            test_parser = FuzzingLogParser(self.get_network_log_path(experiments_dir, logger.LOG_TYPE_TESTING), max_seq=Num_Sequences)
            #test_parser = FuzzingLogParser("D:\\git\\restler-fuzzer\\restler\\RestlerResults\\experiment31916\\logs\\network.testing.23496.1.txt", max_seq=Num_Sequences)
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
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar.py")}',
            '--enable_checkers', 'payloadbody'
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
        args = Common_Settings + [
            '--fuzzing_mode', 'directed-smoke-test',
            '--restler_grammar', f'{os.path.join(Test_File_Directory, "test_grammar_body.py")}',
            '--enable_checkers', 'payloadbody'
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
