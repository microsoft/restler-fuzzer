# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
import os

from unittest.mock import mock_open

from test_servers.parsed_requests import *
from test_servers.log_parser import *

LOG_DIR = 'test_logs'

class LogParserTest(unittest.TestCase):
    def test_get_request_sending(self):
        parser = LogParser("")
        req = ParsedRequest('PUT /city/cityName-63a4e53554/house/houseName-31cdd4b5e6 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        req_bad = ParsedRequest('GET /city/cityName-63a4e53554/house/houseName-31cdd4b5e6 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        get_req = parser._get_request("2020-07-21 08:00:22.584: Sending: 'PUT /city/cityName-63a4e53554/house/houseName-31cdd4b5e6 HTTP/1.1\\r\\nContent-Length: 4\\r\\n\\r\\n{}\\r\\n'\n", True)
        get_req_bad = parser._get_request("2020-07-21 08:00:22.584: Sending: 'PUT /city/cityName-63a4e53554 HTTP/1.1\\r\\nContent-Length: 4\\r\\n\\r\\n{}\\r\\n'\n", True)
        self.assertEqual(req, get_req)
        self.assertNotEqual(req_bad, get_req)
        self.assertNotEqual(req, get_req_bad)

    def test_get_request_no_sending(self):
        parser = LogParser("")
        req = ParsedRequest('PUT /city/cityName-63a4e53554/house/houseName-31cdd4b5e6 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        get_req = parser._get_request("PUT /city/cityName-63a4e53554/house/houseName-31cdd4b5e6 HTTP/1.1\\r\\nContent-Length: 4\\r\\n\\r\\n{}\\r\\n\\n")
        self.assertEqual(req, get_req)

class FuzzingLogParserTest(unittest.TestCase):
    def test_parse(self):
        req1 = ParsedRequest('PUT /city/cityName-63a4e53554/house/houseName-31cdd4b5e6 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        req2 = ParsedRequest('PUT /city/cityName-63a4e53554/house/houseName-31cdd4b5e6/color/colorName-34782542d1 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{{\r\n')
        seq1 = ParsedSequence([req1, req2])
        seq1.checker_requests['LeakageRule'] = []
        seq1.checker_requests['ResourceHierarchy'] = []
        seq1.checker_requests['UseAfterFree'] = []
        seq1.checker_requests['NameSpaceRule'] = []
        seq1.checker_requests['InvalidDynamicObject'] = []
        seq1.checker_requests['PayloadBody'] = []
        seq1.checker_requests['Examples'] = []
        req1 = ParsedRequest('PUT /city/cityName-63a4e53554/house/houseName-ac5a89e704 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        req2 = ParsedRequest('GET /city/cityName-63a4e53554/house/houseName-ac5a89e704 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        seq2 = ParsedSequence([req1, req2])
        check1 = ParsedRequest('PUT /city/cityName-63a4e53554/house/houseName-7db9fa94c7 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        check2 = ParsedRequest('GET /city/cityName-63a4e53554/house/houseName-7db9fa94c7?api-version=2019-01-01 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        check3 = ParsedRequest('GET /city/cityName-63a4e53554/house/houseName-7db9fa94c7/?/ HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        check4 = ParsedRequest('GET /city/cityName-63a4e53554/house/houseName-7db9fa94c7?? HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        check5 = ParsedRequest('GET /city/cityName-63a4e53554/house/houseName-7db9fa94c7/houseName-7db9fa94c7 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        check6 = ParsedRequest('GET /city/cityName-63a4e53554/house/{} HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        seq2.checker_requests['LeakageRule'] = []
        seq2.checker_requests['ResourceHierarchy'] = []
        seq2.checker_requests['UseAfterFree'] = []
        seq2.checker_requests['NameSpaceRule'] = []
        seq2.checker_requests['InvalidDynamicObject'] = [check1, check2, check3, check4, check5, check6]
        seq2.checker_requests['PayloadBody'] = []
        seq2.checker_requests['Examples'] = []
        req1 = ParsedRequest('PUT /useafterfreetest/useafterfreeTest-87c1bb88f2 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        req2 = ParsedRequest('DELETE /useafterfreetest/useafterfreeTest-87c1bb88f2 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        seq3 = ParsedSequence([req1, req2])
        use1 = ParsedRequest('GET /useafterfreetest/useafterfreeTest-87c1bb88f2 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        inv1 = ParsedRequest('PUT /useafterfreetest/useafterfreeTest-268f5f47d2 HTTP/1.1\r\nContent-Length: 4\r\n\r\n{}\r\n')
        inv2 = ParsedRequest('DELETE /useafterfreetest/useafterfreeTest-268f5f47d2?api-version=2019-01-01 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        inv3 = ParsedRequest('DELETE /useafterfreetest/useafterfreeTest-268f5f47d2/?/ HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        inv4 = ParsedRequest('DELETE /useafterfreetest/useafterfreeTest-268f5f47d2?? HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        inv5 = ParsedRequest('DELETE /useafterfreetest/useafterfreeTest-268f5f47d2/useafterfreeTest-268f5f47d2 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        inv6 = ParsedRequest('DELETE /useafterfreetest/{} HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        seq3.checker_requests['LeakageRule'] = []
        seq3.checker_requests['ResourceHierarchy'] = []
        seq3.checker_requests['UseAfterFree'] = [use1]
        seq3.checker_requests['NameSpaceRule'] = []
        seq3.checker_requests['InvalidDynamicObject'] = [inv1, inv2, inv3, inv4, inv5, inv6]
        seq3.checker_requests['PayloadBody'] = []
        seq3.checker_requests['Examples'] = []
        seq_list = [seq1, seq2, seq3]

        parser = FuzzingLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, "fuzzing_log.txt"))
        self.assertEqual(seq_list, parser._seq_list)
        # Test checker order parsing
        del seq3.checker_requests['NameSpaceRule']
        seq3.checker_requests['NameSpaceRule'] = []
        self.assertNotEqual(seq_list, parser._seq_list)
        # Test missing sequence
        seq_list_bad = [seq1, seq2]
        self.assertNotEqual(seq_list_bad, parser._seq_list)

    def test_diff(self):
        parser = FuzzingLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, "fuzzing_log.txt"))
        parser2 = FuzzingLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, "fuzzing_log.txt"))
        parser3 = FuzzingLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, "fuzzing_log_2.txt"))
        parser4 = FuzzingLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, "fuzzing_log_3.txt"))
        self.assertTrue(parser.diff_log(parser2))
        self.assertFalse(parser.diff_log(parser3))
        self.assertFalse(parser.diff_log(parser4))

    def test_parse_exception(self):
        with self.assertRaises(TestFailedException):
            parser = FuzzingLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, "fuzzing_log_bad.txt"))

class GarbageCollectorLogParserTest(unittest.TestCase):
    def test_parse(self):
        parser = GarbageCollectorLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'gc_log.txt'))
        req1 = ParsedRequest('DELETE /resourcehierarchytest/resourcehierarchyTest-ed70be9d51 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        req2 = ParsedRequest('DELETE /resourcehierarchytest/resourcehierarchyTest-ef837e2d50 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        req3 = ParsedRequest('DELETE /resourcehierarchytest/resourcehierarchyTest-123456 HTTP/1.1\r\nContent-Length: 0\r\n\r\n')
        req_set = {
            req1,
            req1,
            req2,
            req2
        }
        self.assertEqual(parser._req_set, req_set)
        # Test shortened list
        req_set.remove(req2)
        self.assertNotEqual(parser._req_set, req_set)
        # Test extended list
        req_set.add(req3)
        self.assertNotEqual(parser._req_set, req_set)

    def test_diff(self):
        parser = GarbageCollectorLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'gc_log.txt'))
        parser2 = GarbageCollectorLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'gc_log.txt'))
        parser3 = GarbageCollectorLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'gc_log_2.txt'))
        self.assertTrue(parser.diff_log(parser2))
        self.assertFalse(parser.diff_log(parser3))
        self.assertFalse(parser3.diff_log(parser))

    def test_parse_exception(self):
        with self.assertRaises(TestFailedException):
            GarbageCollectorLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'gc_log_bad.txt'))

class BugLogParserTest(unittest.TestCase):
    def test_parse(self):
        main_seq = (ParsedSequence([
            ParsedRequest('PUT /city/cityName-63a4e53554/house/houseName HTTP/1.1\r\n\r\n{}\r\n'),
            ParsedRequest('PUT /city/cityName-63a4e53554/house/_READER_DELIM_city_house_put_name_READER_DELIM/color/colorName HTTP/1.1\r\n\r\n{{\r\n')
        ]), True, 'main_driver_500_a6e432e533efe1aa006445e4d76075393bc0848f')
        leak_seq = (ParsedSequence([
            ParsedRequest('PUT /leakageruletest/leakageTest HTTP/1.1\r\n\r\n{}\r\n'),
            ParsedRequest('GET /leakageruletest/_READER_DELIM_leakageruletest_put_name_READER_DELIM HTTP/1.1\r\n\r\n'),
        ]), True, 'LeakageRuleChecker_20x_862884a058ddaaebe2c8d479c75b44b294ff4684')
        resource_seq = (ParsedSequence([
            ParsedRequest('PUT /resourcehierarchytest/resourcehierarchyTest HTTP/1.1\r\n\r\n{}\r\n'),
            ParsedRequest('GET /resourcehierarchytest/_READER_DELIM_resourcehierarchytest_put_name_READER_DELIM/resourcehierarchychild/_READER_DELIM_resourcehierarchychild_put_name_READER_DELIM HTTP/1.1\r\n\r\n')
        ]), True, 'ResourceHierarchyChecker_20x_cf94181e3d6bf39620706486f6c4af575c83a5ea')
        use_seq = (ParsedSequence([
            ParsedRequest('PUT /useafterfreetest/useafterfreeTest HTTP/1.1\r\n\r\n{}\r\n'),
            ParsedRequest('DELETE /useafterfreetest/_READER_DELIM_useafterfreetest_put_name_READER_DELIM HTTP/1.1\r\n\r\n'),
            ParsedRequest('GET /useafterfreetest/_READER_DELIM_useafterfreetest_put_name_READER_DELIM HTTP/1.1\r\n\r\n')
        ]), True, 'UseAfterFreeChecker_20x_8ccb62ff5e82bc905b633f5c228fecaf59b8c379')
        inv_seq1 = (ParsedSequence([
            ParsedRequest('PUT /resourcehierarchytest/resourcehierarchyTest HTTP/1.1\r\n\r\n{}\r\n'),
            ParsedRequest('PUT /resourcehierarchytest/_READER_DELIM_resourcehierarchytest_put_name_READER_DELIM/resourcehierarchychild/resourcehierarchyChild HTTP/1.1\r\n\r\n{}\r\n')
        ]), True, 'InvalidDynamicObjectChecker_20x_0c7bc79adedde76524a357aaa4f73dc367f6a19d')
        inv_seq2 = (ParsedSequence([
            ParsedRequest('PUT /resourcehierarchytest/resourcehierarchyTest HTTP/1.1\r\n\r\n{}\r\n'),
            ParsedRequest('PUT /resourcehierarchytest/_READER_DELIM_resourcehierarchytest_put_name_READER_DELIM/resourcehierarchychild/resourcehierarchyChild HTTP/1.1\r\n\r\n{}\r\n'),
            ParsedRequest('DELETE /resourcehierarchytest/_READER_DELIM_resourcehierarchytest_put_name_READER_DELIM/resourcehierarchychild/_READER_DELIM_resourcehierarchychild_put_name_READER_DELIM HTTP/1.1\r\n\r\n')
        ]), False, 'InvalidDynamicObjectChecker_20x_9bf2a8c3595768ecbf532ec3368a7854e74ff5b1')

        bug_list = {
            'main_driver_500': [main_seq],
            'LeakageRuleChecker': [leak_seq],
            'ResourceHierarchyChecker': [resource_seq],
            'UseAfterFreeChecker': [use_seq],
            'InvalidDynamicObjectChecker': [inv_seq1, inv_seq2]
        }

        parser = BugLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'bug_buckets.txt'))
        self.assertEqual(parser._bug_list, bug_list)
        # Test extra sequence
        bug_list['InvalidDynamicObjectChecker'].append(inv_seq2)
        self.assertNotEqual(parser._bug_list, bug_list)
        # Test one less sequence
        bug_list['InvalidDynamicObjectChecker'] = [inv_seq1]
        self.assertNotEqual(parser._bug_list, bug_list)
        # Test reproduced vs not reproduced
        inv_seq2 = list(inv_seq2)
        inv_seq2[1] = True
        bug_list['InvalidDynamicObjectChecker'].append(tuple(inv_seq2))
        self.assertNotEqual(parser._bug_list, bug_list)
        # Test hash mismatch
        inv_seq2[1] = False
        inv_seq2[2] = 'InvalidDynamicObjectChecker_20x_9bf2a8c3595768ecbf532ec3368a7854e74ffbad'
        bug_list['InvalidDynamicObjectChecker'] = [inv_seq1, inv_seq2]
        self.assertNotEqual(parser._bug_list, bug_list)

    def test_diff(self):
        parser = BugLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'bug_buckets.txt'))
        parser2 = BugLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'bug_buckets.txt'))
        # Fewer sequences
        parser3 = BugLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'bug_buckets2.txt'))
        # Reproduce doesn't match
        parser4 = BugLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'bug_buckets3.txt'))
        # Hash doesn't match
        parser5 = BugLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'bug_buckets4.txt'))
        self.assertTrue(parser.diff_log(parser2))
        self.assertFalse(parser.diff_log(parser3))
        self.assertFalse(parser3.diff_log(parser))
        self.assertFalse(parser.diff_log(parser4))
        self.assertFalse(parser.diff_log(parser5))

    def test_parse_exception(self):
        with self.assertRaises(TestFailedException):
            BugLogParser(os.path.join(os.path.dirname(__file__), LOG_DIR, 'bug_buckets_bad.txt'))