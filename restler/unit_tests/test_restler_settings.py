# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Unit tests for the RestlerSettings class """
import unittest
import json
import os
import re
import restler_settings

from engine import primitives
from engine.transport_layer.response import HttpResponse
from engine.core.request_utilities import str_to_hex_def as hex_def
from restler_settings import RestlerSettings
from restler_settings import NewSingletonError
from restler_settings import UninitializedError
from restler_settings import InvalidValueError
from restler_settings import OptionValidationError

class RestlerSettingsTest(unittest.TestCase):
    def tearDown(self):
        RestlerSettings.TEST_DeleteInstance()

    def test_single_instance(self):
        settings1 = RestlerSettings({})
        settings2 = RestlerSettings.Instance()

        self.assertEqual(settings1, settings2)
        with self.assertRaises(NewSingletonError):
            # Test can't create new instance
            RestlerSettings({})

    def test_not_yet_initialzed(self):
        with self.assertRaises(UninitializedError):
            settings = RestlerSettings.Instance()

    def test_empty_settings_file(self):
        settings = RestlerSettings({})
        self.assertEqual(0, settings.get_producer_timing_delay(10))

    def test_commmand_line_producer_timing_delay(self):
        user_args = {'producer_timing_delay' : 1}
        settings = RestlerSettings(user_args)
        self.assertEqual(1, settings.get_producer_timing_delay(0))

    def test_per_resource_timing_delays(self):
        request_endpoint1 = 'test/{testSomething}/moreTest'
        request_endpoint2 = 'different/{other}/somethingElse'
        request_endpoint3 = 'final/{testing}/theEnd'
        settings_file = {
                    'global_producer_timing_delay': 5,
                    'per_resource_settings': {
                        request_endpoint1: {
                            'producer_timing_delay': 3
                        },
                        request_endpoint2: {
                            'producer_timing_delay': 7
                        }
                    }
                }
        user_args = {'producer_timing_delay' : 1}
        user_args.update(settings_file)
        settings = RestlerSettings(user_args)
        # Set in settings file
        self.assertEqual(3, settings.get_producer_timing_delay(hex_def(request_endpoint1)))
        # Set in settings file (different value)
        self.assertEqual(7, settings.get_producer_timing_delay(hex_def(request_endpoint2)))
        # Not set in settings file
        self.assertEqual(5, settings.get_producer_timing_delay(hex_def(request_endpoint3)))

    def test_default_version(self):
        user_args = {}
        settings = RestlerSettings(user_args)
        self.assertEqual('0.0.0', settings.version)

    def test_set_version(self):
        user_args = {'set_version' : '5.3.0'}
        settings = RestlerSettings(user_args)
        self.assertEqual('5.3.0', settings.version)

    def test_max_async_wait_time(self):
        request_endpoint1 = 'test/{testSomething}/moreTest'
        request_endpoint2 = 'different/{other}/somethingElse'
        request_endpoint3 = 'final/{testing}/theEnd'
        settings_file = {
                    'global_producer_timing_delay': 5,
                    'per_resource_settings': {
                        request_endpoint1: {
                            'producer_timing_delay': 3
                        },
                        request_endpoint2: {
                            'producer_timing_delay': 7
                        }
                    },
                    'max_async_resource_creation_time': 6
                }
        user_args = {}
        user_args.update(settings_file)
        settings = RestlerSettings(user_args)
        self.assertEqual(6, settings.get_max_async_resource_creation_time(hex_def(request_endpoint1)))
        # producer timing delay > max async
        self.assertEqual(7, settings.get_max_async_resource_creation_time(hex_def(request_endpoint2)))
        self.assertEqual(6, settings.get_max_async_resource_creation_time(hex_def(request_endpoint3)))

    def test_max_combinations_in_settings(self):
        settings_file = {
            'settings_file_exists': True,
            'max_combinations': 10
            }
        settings = RestlerSettings(settings_file)
        candidate_values = primitives.CandidateValuesPool()
        test_dict = {
                    }
        candidate_values.set_candidate_values(test_dict)
        self.assertEqual(10, settings.max_combinations)

    def test_command_line_max_request_execution_time(self):
        user_args = {'max_request_execution_time': 15}
        settings = RestlerSettings(user_args)
        self.assertEqual(15, settings.max_request_execution_time)

    def test_max_request_execution_time(self):
        user_args = {'max_request_execution_time': 15}
        settings_file = {
            'max_request_execution_time' : 12
        }
        user_args.update(settings_file)
        settings = RestlerSettings(user_args)
        self.assertEqual(12, settings.max_request_execution_time)

    def test_invalid_max_request_execution_time(self):
        user_args = {'max_request_execution_time' : 0}
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)
        settings_file = {
            'max_request_execution_time' : -1
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(settings_file)
        user_args = {'max_request_execution_time': restler_settings.MAX_REQUEST_EXECUTION_TIME_MAX+1}
        settings_file = {
            'max_request_execution_time' : restler_settings.MAX_REQUEST_EXECUTION_TIME_MAX+1
        }
        user_args.update(settings_file)
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

    def test_create_once(self):
        request_endpoint1 = 'test/{testSomething}/moreTest'
        request_endpoint2 = 'different/{other}/somethingElse'
        request_endpoint3 = 'final/{testing}/theEnd'

        settings_file = {
            'per_resource_settings': {
                request_endpoint1: {
                    'create_once': 1
                },
                request_endpoint2: {
                    'create_once': 1
                },
                request_endpoint3: {
                    'create_once': 0
                }
            }
        }

        RestlerSettings(settings_file)
        create_once_list = RestlerSettings.Instance().create_once_endpoints

        self.assertEqual(2, len(create_once_list))

        self.assertEqual(True, hex_def(request_endpoint1) in create_once_list)
        self.assertEqual(True, hex_def(request_endpoint2) in create_once_list)
        self.assertNotEqual(True, hex_def(request_endpoint3) in create_once_list)

    def test_custom_dictionaries(self):
        request_endpoint1 = 'test/{testSomething}/moreTest'
        request_endpoint2 = 'different/{other}/somethingElse'
        request_endpoint3 = 'final/{testing}/theEnd'
        dict1 = "dict1.json"
        dict2 = "dict2.json"

        settings_file = {
            'per_resource_settings': {
                request_endpoint1: {
                    'custom_dictionary': dict1
                },
                request_endpoint2: {
                    'custom_dictionary': dict2
                },
                request_endpoint3: {
                }
            }
        }

        RestlerSettings(settings_file)
        custom_dicts = RestlerSettings.Instance().get_endpoint_custom_mutations_paths()

        self.assertEqual(2, len(custom_dicts))
        self.assertEqual(dict1, custom_dicts[hex_def(request_endpoint1)])
        self.assertEqual(dict2, custom_dicts[hex_def(request_endpoint2)])
        self.assertTrue(hex_def(request_endpoint3) not in custom_dicts)

    def test_checkers_in_settings(self):
        settings_file = {
                    'settings_file_exists':True,
                    'checkers' :
                    {
                        'NamespaceRule' : {
                            'mode' : 'exhaustive'
                        },
                        'useafterfree' : {
                            'mode' : 'exhaustive'
                        },
                        'leakagerule' : {
                            'mode' : 'exhaustive'
                        },
                        'resourcehierarchy' : {
                            'mode' : 'exhaustive'
                        }
                    }
                }

        settings = RestlerSettings(settings_file)
        candidate_values = primitives.CandidateValuesPool()
        test_dict = {
                    }
        candidate_values.set_candidate_values(test_dict)
        self.assertEqual('exhaustive', settings.get_checker_arg('namespacerule', 'mode'))
        self.assertEqual('exhaustive', settings.get_checker_arg('USEAFTERFREE', 'mode'))
        self.assertEqual('exhaustive', settings.get_checker_arg('LeakageRule', 'mode'))
        self.assertEqual('exhaustive', settings.get_checker_arg('resourcehierarchy', 'mode'))
        self.assertEqual(None, settings.get_checker_arg('namespace_rule_mode', 'mode'))
        self.assertEqual(None, settings.get_checker_arg('use_after_free_rule_mode', 'mode'))
        self.assertEqual(None, settings.get_checker_arg('leakage_rule_mode', 'mode'))
        self.assertEqual(None, settings.get_checker_arg('resource_hierarchy_rule_mode', 'mode'))

    def test_invalid_entries(self):
        user_args = {
            'max_sequence_length': '10'
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            'max_sequence_length': -1
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            'target_port': 2**16
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            "checkers": 5
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            "checkers": [5]
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            "checkers" : {
                "namespacerule": 5
            }
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            'per_resource_settings': {
                'producer_timing_delay': 5
            }
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            'per_resource_settings': {
                'endpoint': {
                    'producer_timing_delay': [5]
                }
            }
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

        user_args = {
            'per_resource_settings': {
                'endpoint': {
                    'producer_timing_delay': "somestring"
                }
            }
        }
        with self.assertRaises(InvalidValueError):
            RestlerSettings(user_args)

    def test_random_walk_sequence_length(self):
        user_args = {'target_port': 500,
                     'target_ip': '192.168.0.1',
                     'fuzzing_mode': 'random-walk',
                     'max_sequence_length': 50}
        settings = RestlerSettings(user_args)
        with self.assertRaises(OptionValidationError):
            settings.validate_options()

    def test_refresh_cmd_no_interval(self):
        user_args = {'target_port': 500,
                     'target_ip': '192.168.0.1',
                     'token_refresh_cmd': 'some command'}
        settings = RestlerSettings(user_args)
        with self.assertRaises(OptionValidationError):
            settings.validate_options()

    def test_refresh_interval_no_cmd(self):
        user_args = {'target_port': 500,
                     'target_ip': '192.168.0.1',
                     'token_refresh_interval': 30}
        settings = RestlerSettings(user_args)
        with self.assertRaises(OptionValidationError):
            settings.validate_options()

    def test_throttling_multiple_fuzzing_jobs(self):
        user_args = {'target_port': 500,
                     'target_ip': '192.168.0.1',
                     'token_refresh_cmd': 'some command',
                     'token_refresh_interval': 30,
                     'fuzzing_mode': 'random-walk',
                     'fuzzing_jobs': 2,
                     'request_throttle_ms': 100}

        settings = RestlerSettings(user_args)
        with self.assertRaises(OptionValidationError):
            settings.validate_options()

    def test_valid_option_validation(self):
        user_args = {'target_port': 500,
                     'target_ip': '192.168.0.1',
                     'token_refresh_cmd': 'some command',
                     'token_refresh_interval': 30,
                     'fuzzing_mode': 'random-walk'}
        try:
            settings = RestlerSettings(user_args)
            settings.validate_options()
        except:
            assert False

        settings.TEST_DeleteInstance()

        user_args = {'target_port': 500,
                     'target_ip': '192.168.0.1'}

        try:
            settings = RestlerSettings(user_args)
            settings.validate_options()
        except:
            assert False

    def test_custom_bug_codes(self):
        user_args = {"custom_bug_codes": ["200", "4?4", "3*"]}
        try:
            settings = RestlerSettings(user_args)
            settings.validate_options()
        except:
            assert False

        response200 = HttpResponse('HTTP/1.1 200 response')
        response201 = HttpResponse('HTTP/1.1 201 response')
        response400 = HttpResponse('HTTP/1.1 400 response')
        response404 = HttpResponse('HTTP/1.1 404 response')
        response414 = HttpResponse('HTTP/1.1 414 response')
        response300 = HttpResponse('HTTP/1.1 300 response')
        response301 = HttpResponse('HTTP/1.1 301 response')
        response500 = HttpResponse('HTTP/1.1 500 response')

        self.assertTrue(response200.has_bug_code())
        self.assertFalse(response201.has_bug_code())
        self.assertFalse(response400.has_bug_code())
        self.assertTrue(response404.has_bug_code())
        self.assertTrue(response414.has_bug_code())
        self.assertTrue(response300.has_bug_code())
        self.assertTrue(response301.has_bug_code())
        self.assertTrue(response500.has_bug_code())

    def test_custom_non_bug_codes(self):
        user_args = {"custom_non_bug_codes": ["200", "4?4", "3*"]}
        try:
            settings = RestlerSettings(user_args)
            settings.validate_options()
        except:
            assert False

        response200 = HttpResponse('HTTP/1.1 200 response')
        response201 = HttpResponse('HTTP/1.1 201 response')
        response400 = HttpResponse('HTTP/1.1 400 response')
        response404 = HttpResponse('HTTP/1.1 404 response')
        response414 = HttpResponse('HTTP/1.1 414 response')
        response300 = HttpResponse('HTTP/1.1 300 response')
        response301 = HttpResponse('HTTP/1.1 301 response')
        response500 = HttpResponse('HTTP/1.1 500 response')

        self.assertFalse(response200.has_bug_code())
        self.assertTrue(response201.has_bug_code())
        self.assertTrue(response400.has_bug_code())
        self.assertFalse(response404.has_bug_code())
        self.assertFalse(response414.has_bug_code())
        self.assertFalse(response300.has_bug_code())
        self.assertFalse(response301.has_bug_code())
        self.assertTrue(response500.has_bug_code())

        settings.TEST_DeleteInstance()

        user_args["custom_non_bug_codes"].append("500")
        try:
            settings = RestlerSettings(user_args)
            settings.validate_options()
        except:
            assert False

        self.assertFalse(response500.has_bug_code())

    def test_custom_bug_code_list_mutual_exclusiveness(self):
        user_args = {"custom_bug_codes": ["200", "4?4", "3*"],
                     "custom_non_bug_codes": ["500"]}

        settings = RestlerSettings(user_args)
        with self.assertRaises(OptionValidationError):
            settings.validate_options()

    def test_settings_file_upload(self):
        with open(os.path.join(os.path.dirname(__file__), "restler_user_settings.json")) as json_file:
            settings_file = json.load(json_file)
        settings = RestlerSettings(settings_file)

        self.assertEqual('exhaustive', settings.get_checker_arg('namespacerule', 'mode'))
        self.assertEqual('exhaustive', settings.get_checker_arg('useafterfree', 'mode'))
        self.assertEqual('exhaustive', settings.get_checker_arg('leakagerule', 'mode'))
        self.assertEqual('exhaustive', settings.get_checker_arg('resourcehierarchy', 'mode'))
        self.assertEqual(None, settings.get_checker_arg('invaliddynamicobject', 'mode'))
        self.assertEqual('normal', settings.get_checker_arg('payloadbody', 'mode'))
        self.assertTrue(settings.get_checker_arg('payloadbody', 'start_with_valid'))
        self.assertTrue(settings.get_checker_arg('payloadbody', 'start_with_examples'))
        self.assertFalse(settings.get_checker_arg('payloadbody', 'size_dep_budget'))
        self.assertTrue(settings.get_checker_arg('payloadbody', 'use_feedback'))
        self.assertEqual('C:\\restler\\restlerpayloadbody\\recipe_custom.json', settings.get_checker_arg('payloadbody', 'recipe_file'))

        request1 = "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/dnsZones/{zoneName}/{recordType}/{relativeRecordSetName}"
        request2 = "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/dnsZones/{zoneName}"
        self.assertEqual(1, settings.get_producer_timing_delay(hex_def(request1)))
        self.assertEqual(5, settings.get_producer_timing_delay(hex_def(request2)))
        self.assertEqual(2, settings.get_producer_timing_delay(hex_def("test_unknown_request_id")))

        custom_dicts = settings.get_endpoint_custom_mutations_paths()
        self.assertEqual("c:\\restler\\custom_dict1.json", custom_dicts[hex_def(request1)])
        self.assertEqual("c:\\restler\\custom_dict2.json", custom_dicts[hex_def(request2)])

        self.assertEqual(20, settings.max_combinations)
        self.assertEqual(90, settings.max_request_execution_time)

        self.assertEqual(True, hex_def(request1) in settings.create_once_endpoints)
        self.assertNotEqual(True, hex_def(request2) in settings.create_once_endpoints)

        self.assertEqual(200, settings.dyn_objects_cache_size)
        self.assertEqual(2, settings.fuzzing_jobs)
        self.assertEqual('directed-smoke-test', settings.fuzzing_mode)
        self.assertEqual(30, settings.garbage_collection_interval)
        self.assertTrue(settings.ignore_dependencies)
        self.assertTrue(settings.ignore_feedback)
        self.assertTrue(settings.connection_settings.include_user_agent)
        self.assertEqual(45, settings.max_async_resource_creation_time)
        self.assertEqual(11, settings.max_sequence_length)
        self.assertFalse(settings.connection_settings.use_ssl)
        self.assertTrue(settings.connection_settings.disable_cert_validation)
        self.assertTrue(settings.no_tokens_in_logs)
        self.assertEqual('(\w*)/ddosProtectionPlans(\w*)', settings.path_regex)
        self.assertEqual(500, settings.request_throttle_ms)
        self.assertEqual('100.100.100.100', settings.connection_settings.target_ip)
        self.assertEqual(500, settings.connection_settings.target_port)
        self.assertEqual(12, settings.time_budget)
        self.assertEqual('some refresh command', settings.token_refresh_cmd)
        self.assertEqual(60, settings.token_refresh_interval)
        self.assertEqual(False, settings.wait_for_async_resource_creation)
        self.assertEqual('0.0.0', settings.version)
        code1 = re.compile('400')
        code2 = re.compile('2.4')
        code3 = re.compile('3.+')
        code4 = re.compile('404')
        code5 = re.compile('500')
        self.assertEqual([code1, code2, code3], settings.custom_bug_codes)
        self.assertEqual([code4, code5], settings.custom_non_bug_codes)
