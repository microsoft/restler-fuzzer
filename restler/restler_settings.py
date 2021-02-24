# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Holds user-defined settings data """
from __future__ import print_function
import json
import sys
import re

class NewSingletonError(Exception):
    pass

class UninitializedError(Exception):
    pass

class InvalidValueError(Exception):
    pass

class OptionValidationError(Exception):
    pass

class ConnectionSettings(object):
    def __init__(self, target_ip, target_port, use_ssl=True, include_user_agent=False, disable_cert_validation=False):
        """ Initializes an object that contains the connection settings for the socket
        @param target_ip: The ip of the target service.
        @type  target_ip: Str
        @param target_port: The port of the target service.
        @type  target_port: Str
        @param use_ssl: Whether or not to use SSL for socket connection
        @type  use_ssl: Boolean
        @param include_user_agent: Whether or not to add User-Agent to request headers
        @type  include_user_agent: Boolean
        @param disable_cert_validation: Whether or not to disable SSL certificate validation
        @type  disable_cert_validation: Bool

        @return: None
        @rtype : None

        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.use_ssl = use_ssl
        self.include_user_agent = include_user_agent
        self.disable_cert_validation = disable_cert_validation

class SettingsArg(object):
    """ Holds a setting's information """
    def __init__(self, name, type, default, user_args, minval=None, min_exactok=True, maxval=None, max_exactok=True, val_convert=None):
        """ Initializes a SettingsArg with its name, type, default value, and restraints.

        @param name: The name of the arg (as referenced in the settings file)
        @type  name: Str
        @param type: The type of the setting's value's variable (int, bool, etc)
        @type  type: Type
        @param default: The default value of the setting's value.
        @type  default: @param type
        @param user_args: The dictionary of user arguments (from settings file and command-line)
        @type  user_args: Dict or None
        @param minval: The minimum value allowed
        @type  minval: @param type
        @param min_exactok: If False, value must exceed minimum
        @type  min_exactok: Bool
        @param maxval: The maximum value allowed
        @type  maxval: @param type
        @param max_exactok: If False, value must be less than maximum
        @type  max_exactok: Bool
        @param val_convert: A function used to convert the value
        @type  val_convert: Func

        """
        self.name = name
        self.type = type
        self.default = default
        self.minval = minval
        self.min_exactok = min_exactok
        self.maxval = maxval
        self.max_exactok = max_exactok
        self.val_convert = val_convert
        self.val = default

        self._set_arg(user_args)

    def _set_arg(self, user_args):
        """ Helper that updates the val if it was set by the user

        @param user_args: The dictionary of user arguments (from settings file and command-line)
        @type  user_args: Dict or None

        @return: None
        @rtype : None

        """
        if user_args and self.name in user_args and user_args[self.name] is not None:
            self.set_val(user_args[self.name])

    def set_val(self, value):
        """ Sets the SettingArg's value after validating it

        @param val: The new value to set
        @type  val: self.type

        @return: None
        @rtype : None

        """
        if self.val_convert:
            value = self.val_convert(value)
        if value != None:
            self._validate(value)
        self.val = value

    def get_val(self):
        """ Return's the SettingArg's value

        @return: The SettingArg's value
        @rtype : self.type

        """
        return self.val

    def _validate(self, value):
        """ Verifies that a new value is compatible with this SettingsArg.
        Checks its type and whether it is >= min and <= max.
        Will raise InvalidValueError if validation fails.

        @param value: The value to validate
        @type  value: Unknown, but should be self.type

        @return: None
        @rtype : None

        """
        if not isinstance(value, self.type):
            raise InvalidValueError(f"{self.name} was an invalid type, should be {self.type}. "
                                    f"Value input: {value}, Type: {type(value)}")
        if self.minval != None:
            if self.min_exactok:
                if value < self.minval:
                    raise InvalidValueError(f"{self.name} must be at least {self.minval} "
                                            f"(default: {self.default}). Value input: {value}")
            elif value <= self.minval:
                raise InvalidValueError(f"{self.name} must be greater than {self.minval} "
                                        f"(default: {self.default}). Value input: {value}")
        if self.maxval != None:
            if self.max_exactok:
                if value > self.maxval:
                    raise InvalidValueError(f"{self.name} must not exceed {self.maxval} "
                                            f"(default: {self.default}). Value input: {value}")
            elif value >= self.maxval:
                raise InvalidValueError(f"{self.name} must be less than {self.maxval} "
                                        f"(default: {self.default}). Value input: {value}")

class SettingsListArg(SettingsArg):
    """ Special SettingsArg type for List values """
    def __init__(self, name, type, user_args, minval=None, min_exactok=True, maxval=None, max_exactok=True, val_convert=None):
        """ Initializes a SettingsListArg object

        @param name: The name of the arg (as referenced in the settings file)
        @type  name: Str
        @param type: The type of each value within the list (NOT just type=list)
        @type  type: Type
        @param user_args: The dictionary of user arguments (from settings file and command-line)
        @type  user_args: Dict or None
        @param minval: The minimum value allowed for each value in the list
        @type  minval: @param type
        @param min_exactok: If False, value must exceed minimum
        @type  min_exactok: Bool
        @param maxval: The maximum value allowed
        @type  maxval: @param type
        @param max_exactok: If False, value must be less than maximum
        @type  max_exactok: Bool
        @param val_convert: A function used to convert the values
        @type  val_convert: Func

        """
        super(SettingsListArg, self).__init__(name, type, None, None, minval=minval, min_exactok=min_exactok, maxval=maxval, max_exactok=max_exactok)
        self.val = []
        self.val_convert = val_convert
        self._set_arg(user_args)

    def __contains__(self, value):
        return value in self.val

    def __iter__(self):
        return iter(self.val)

    def __len__(self):
        return len(self.val)

    def __getitem__(self, index):
        return self.val[index]

    def set_val(self, values):
        """ Validates each element of a list before setting this object's value

        @param values: The list to set
        @type  values: List[self.type]

        @return: None
        @rtype : None

        """
        if not isinstance(values, list):
            raise InvalidValueError(f"{self.name} must be a list. Type was {type(values)}")

        for value in values:
            if value != None:
                if self.val_convert:
                    value = self.val_convert(value)
                self._validate(value)
            self.val.append(value)

class SettingsDictArg(SettingsArg):
    """ Special SettingsArg for Dict values """
    def __init__(self, name, type, minval=None, min_exactok=True, maxval=None, max_exactok=True, val_convert=None, key_convert=None):
        """ Initializes a SettingsDictArg object

        @param name: The name of the arg (as referenced in the settings file)
        @type  name: Str
        @param type: The type of each value within the dict (NOT just type=dict)
        @type  type: Type
        @param minval: The minimum value allowed for each value in the dict
        @type  minval: @param type
        @param min_exactok: If False, value must exceed minimum
        @type  min_exactok: Bool
        @param maxval: The maximum value allowed
        @type  maxval: @param type
        @param max_exactok: If False, value must be less than maximum
        @type  max_exactok: Bool
        @param val_convert: A function used to convert the values
        @type  val_convert: Func
        @param key_convert: A function used to convert the keys
        @type  key_convert: Func

        """
        super(SettingsDictArg, self).__init__(name, type, None, None, minval=minval, min_exactok=min_exactok, maxval=maxval, max_exactok=max_exactok)
        self.val = dict()
        self.key_convert=key_convert
        self.val_convert=val_convert

    def __contains__(self, value):
        return value in self.val

    def __iter__(self):
        return iter(self.val)

    def __len__(self):
        return len(self._val)

    def __getitem__(self, key):
        return self.get_val(key)

    def set_val(self, value):
        """ Validates each value in the dict before setting the object's value

        @param value: The dict to set
        @type  value: Dict[self.type]

        @return: None
        @rtype : None

        """
        if not isinstance(value, dict):
            raise InvalidValueError(f"{self.name} must be a dictionary type. Type was {type(value)}")

        try:
            for k, v in value.items():
                if v != None:
                    self._validate(v)
                    if self.val_convert:
                        v = self.val_convert(v)
                    if self.key_convert:
                        k = self.key_convert(k)
                self.val[k] = v
        except Exception as error:
            raise InvalidValueError(f"Failed to parse {self.name}: {error!s}")

    def get_val(self, key):
        """ Returns the value from the dict at a specified key

        @param key: The key to check for a value
        @type  key: Any

        @return: The value from the specified key, or a default value
        @rtype : self.type

        """
        return self.val[key] if key in self.val else self.default

DYN_OBJECTS_CACHE_SIZE_DEFAULT = 10
FUZZING_MODE_DEFAULT = 'bfs'
# All below times are in seconds
MAX_GC_CLEANUP_TIME_SECONDS_DEFAULT = 300
MAX_REQUEST_EXECUTION_TIME_MAX = 600
MAX_REQUEST_EXECUTION_TIME_DEFAULT = 120
# This time is used as a max timeout when waiting for resources to be created.
# If the timeout is reached we will stop polling the status, but then immediately
# send the GET request for the endpoint just in case it is now ready.
MAX_ASYNC_RESOURCE_CREATION_TIME_DEFAULT = 20
# This small default for the maximum parameter combinations is intended for
# first-time use, such as in Test mode.  Users are expected to increase this value
# as needed for more extensive fuzzing.
MAX_COMBINATIONS_DEFAULT = 20
MAX_SEQUENCE_LENGTH_DEFAULT = 100
TARGET_PORT_MAX = (1<<16)-1
TIME_BUDGET_DEFAULT = 24.0*30 # ~1 month

DEFAULT_TEST_SERVER_ID = 'unit_test'
DEFAULT_VERSION = '0.0.0'

def Settings():
    """ Accessor for the RestlerSettings singleton """
    return RestlerSettings.Instance()

class RestlerSettings(object):
    __instance = None

    @staticmethod
    def Instance():
        """ Singleton's instance accessor

        @return RestlerSettings instance
        @rtype  RestlerSettings

        """
        if RestlerSettings.__instance == None:
            raise UninitializedError("RestlerSettings not yet initialized.")
        return RestlerSettings.__instance

    @staticmethod
    def TEST_DeleteInstance():
        del RestlerSettings.__instance
        RestlerSettings.__instance = None

    def __init__(self, user_args):
        """ Constructor for RestlerSettings object

        @param user_args: Arguments used to initialize settings.
        @type  user_args: Dict

        @return: None
        @rtype:  None

        """
        def convert_wildcards_to_regex(str_value):
            """ Converts strings with wildcards in '?' and '*' format to regex wildcards """
            if not isinstance(str_value, str):
                raise InvalidValueError("Invalid type identified when converting string to wildcard. "
                                        f"{str_value} is type {type(str_value)}")
            new_value = str_value.replace('?', '.')
            new_value = new_value.replace('*', '.+')
            return re.compile(new_value)

        if RestlerSettings.__instance:
            raise NewSingletonError("Attempting to create a new singleton instance.")

        from engine.core.request_utilities import str_to_hex_def
        ## Custom checker arguments
        self._checker_args = SettingsDictArg('checkers', dict)
        if self._checker_args.name in user_args:
            self._checker_args.set_val(user_args[self._checker_args.name])
            self._checker_args.val = { checker_name.lower(): arg
                for checker_name, arg in self._checker_args.val.items() }

        ## List of endpoints whose resource is to be created only once - Will be set with other per_resource settings
        self._create_once_endpoints = SettingsListArg('create_once', str, None, val_convert=str_to_hex_def)
        ## List of status codes that will be flagged as bugs
        self._custom_bug_codes = SettingsListArg('custom_bug_codes', re.Pattern, user_args, val_convert=convert_wildcards_to_regex)
        ## List of paths to custom checker python files
        self._custom_checkers = SettingsListArg('custom_checkers', str, user_args)
        ## Custom dictionaries for individual endpoints - will be set with other per_resource settings
        self._custom_dictionaries = SettingsDictArg('custom_dictionary', str, key_convert=str_to_hex_def)
        ## List of status codes that represent "non-bugs". All other status codes will be treated as bugs.
        self._custom_non_bug_codes = SettingsListArg('custom_non_bug_codes', re.Pattern, user_args, val_convert=convert_wildcards_to_regex)
        ## Disables SSL certificate validation
        self._disable_cert_validation = SettingsArg('disable_cert_validation', bool, False, user_args)
        ## Max number of objects of one type before deletion by the garbage collector
        self._dyn_objects_cache_size = SettingsArg('dyn_objects_cache_size', int, DYN_OBJECTS_CACHE_SIZE_DEFAULT, user_args, minval=0)
        # The number of simultaneous fuzzing jobs to perform
        self._fuzzing_jobs = SettingsArg('fuzzing_jobs', int, 1, user_args, minval=1)
        ## The fuzzing mode (bfs/bfs-cheap/random-walk/directed-smoke-test)
        self._fuzzing_mode = SettingsArg('fuzzing_mode', str, FUZZING_MODE_DEFAULT, user_args)
        ## Length of time between garbage collection calls (None = no garbage collection)
        self._garbage_collection_interval = SettingsArg('garbage_collection_interval', int, None, user_args, minval=0)
        ## Length of time the garbage collector will attempt to cleanup remaining resources at the end of fuzzing (seconds)
        self._garbage_collector_cleanup_time = SettingsArg('garbage_collector_cleanup_time', int, MAX_GC_CLEANUP_TIME_SECONDS_DEFAULT, user_args, minval=0)
        ## The time interval to wait after a resource-generating producer is executed (in seconds)
        self._global_producer_timing_delay = SettingsArg('global_producer_timing_delay', int, 0, None, minval=0)
        if self._global_producer_timing_delay.name in user_args:
            self._global_producer_timing_delay.set_val(user_args[self._global_producer_timing_delay.name])
        # This is here for backwards compatibility with the command-line
        elif 'producer_timing_delay' in user_args:
            self._global_producer_timing_delay.set_val(user_args['producer_timing_delay'])
        # The path to the grammar.json file
        self._grammar_schema = SettingsArg('grammar_schema', str, None, user_args)
        ## Set to override the Host that's specified in the grammar
        self._host = SettingsArg('host', str, None, user_args)
        ##  Ignore request dependencies
        self._ignore_dependencies = SettingsArg('ignore_dependencies', bool, False, user_args)
        ## Ignore server-side feedback
        self._ignore_feedback = SettingsArg('ignore_feedback', bool, False, user_args)
        ## Include user agent in requests sent
        self._include_user_agent = SettingsArg('include_user_agent', bool, True, user_args)
        ## Maximum time to wait for an asynchronous resource to be created before continuing (seconds)
        self._max_async_resource_creation_time = SettingsArg('max_async_resource_creation_time', (int, float), MAX_ASYNC_RESOURCE_CREATION_TIME_DEFAULT, user_args, minval=0)
        ## Maximum number of parameter value combinations for parameters within a given request payload
        self._max_combinations = SettingsArg('max_combinations', int, MAX_COMBINATIONS_DEFAULT, user_args, minval=0)
        ## Maximum time to wait for a response after sending a request (seconds)
        self._max_request_execution_time = SettingsArg('max_request_execution_time', (int, float), MAX_REQUEST_EXECUTION_TIME_DEFAULT, user_args, minval=0, min_exactok=False, maxval=MAX_REQUEST_EXECUTION_TIME_MAX)
        ## Maximum length of any sequence
        self._max_sequence_length = SettingsArg('max_sequence_length', int, MAX_SEQUENCE_LENGTH_DEFAULT, user_args, minval=0)
        ## Do not use SSL validation
        self._no_ssl = SettingsArg('no_ssl', bool, False, user_args)
        ## Do not print auth token data in logs
        self._no_tokens_in_logs = SettingsArg('no_tokens_in_logs', bool, True, user_args)
        ## Limit restler grammars only to endpoints whose paths contain a given substring
        self._path_regex = SettingsArg('path_regex', str, None, user_args)
        ## Minimum time, in milliseconds, to wait between sending requests
        self._request_throttle_ms = SettingsArg('request_throttle_ms', (int, float), None, user_args, minval=0)
        ## Collection of endpoint specific producer timing delays - will be set with other per_resource settings
        self._resource_producer_timing_delays = SettingsDictArg('per_resource_producer_timing_delay', int, key_convert=str_to_hex_def)
        ## If the settings file was used (and not just command-line arguments)
        self._settings_file_exists = SettingsArg('settings_file_exists', bool, False, user_args)
        ## Target IP
        self._target_ip = SettingsArg('target_ip', str, None, user_args)
        ## Target Port
        self._target_port = SettingsArg('target_port', int, None, user_args, minval=0, maxval=TARGET_PORT_MAX)
        ## Set to use test server/run in test mode
        self._use_test_socket = SettingsArg('use_test_socket', bool, False, user_args)
        ## Set the test server identifier
        self._test_server = SettingsArg('test_server', str, DEFAULT_TEST_SERVER_ID, user_args)
        ## Stops fuzzing after given time (hours)
        self._time_budget = SettingsArg('time_budget', (int, float), TIME_BUDGET_DEFAULT, user_args, minval=0)
        ## The command to execute in order to refresh the authentication token
        self._token_refresh_cmd = SettingsArg('token_refresh_cmd', str, None, user_args)
        ## Interval to periodically refresh the authentication token (seconds)
        self._token_refresh_interval = SettingsArg('token_refresh_interval', int, None, user_args)
        ## Restler's version
        self._version = SettingsArg('set_version', str, DEFAULT_VERSION, user_args)
        ## If set, poll for async resource creation before continuing
        self._wait_for_async_resource_creation = SettingsArg('wait_for_async_resource_creation', bool, True, user_args)

        self._connection_settings = ConnectionSettings(self._target_ip.val,
                                        self._target_port.val,
                                        not self._no_ssl.val,
                                        self._include_user_agent.val,
                                        self._disable_cert_validation.val)

        # Set per resource arguments
        if 'per_resource_settings' in user_args:
            self._set_per_resource_args(user_args['per_resource_settings'])

        RestlerSettings.__instance = self

    def __deepcopy__(self, memo):
        """ Don't deepcopy this object, just return its reference """
        return self

    @property
    def connection_settings(self):
        return self._connection_settings

    @property
    def create_once_endpoints(self):
        return self._create_once_endpoints.val

    @property
    def custom_bug_codes(self):
        return self._custom_bug_codes.val

    @property
    def custom_checkers(self):
        return self._custom_checkers.val

    @property
    def custom_non_bug_codes(self):
        return self._custom_non_bug_codes.val

    @property
    def dyn_objects_cache_size(self):
        return self._dyn_objects_cache_size.val

    @property
    def fuzzing_jobs(self):
        return self._fuzzing_jobs.val

    @property
    def fuzzing_mode(self):
        return self._fuzzing_mode.val

    @property
    def garbage_collection_interval(self):
        return self._garbage_collection_interval.val

    @property
    def garbage_collector_cleanup_time(self):
        return self._garbage_collector_cleanup_time.val

    @property
    def grammar_schema(self):
        return self._grammar_schema.val

    @property
    def host(self):
        return self._host.val

    @property
    def ignore_dependencies(self):
        return self._ignore_dependencies.val

    @property
    def ignore_feedback(self):
        return self._ignore_feedback.val

    @property
    def max_async_resource_creation_time(self):
        return self._max_async_resource_creation_time.val

    @property
    def max_combinations(self):
        return self._max_combinations.val

    @property
    def max_request_execution_time(self):
        return self._max_request_execution_time.val

    @property
    def max_sequence_length(self):
        return self._max_sequence_length.val

    @property
    def no_tokens_in_logs(self):
        return self._no_tokens_in_logs.val

    @property
    def path_regex(self):
        return self._path_regex.val

    @property
    def request_throttle_ms(self):
        return self._request_throttle_ms.val

    @property
    def settings_file_exists(self):
        return self._settings_file_exists.val

    @property
    def use_test_socket(self):
        return self._use_test_socket.val

    @property
    def test_server(self):
        return self._test_server.val

    @property
    def time_budget(self):
        return self._time_budget.val

    @property
    def token_refresh_cmd(self):
        return self._token_refresh_cmd.val

    @property
    def token_refresh_interval(self):
        return self._token_refresh_interval.val

    @property
    def version(self):
        return self._version.val

    @property
    def wait_for_async_resource_creation(self):
        return self._wait_for_async_resource_creation.val

    def _set_per_resource_args(self, args: dict):
        """ Sets the per-resource settings

        @param args: The per_resource user arguments
        @return: None

        """
        def _verify_type(n, t, a):
            if not isinstance(a, t):
                raise InvalidValueError(f"{n} must be of {t} type."
                                        f"Received: {a} of type {type(t)}")

        _verify_type('Per Resource arg', dict, args)
        timing_delays = {}
        custom_dicts = {}
        create_once_endpoints = []
        Timing_Delay_Str = 'producer_timing_delay'
        for endpoint in args:
            _verify_type('Per Resource arg', dict, args[endpoint])
            # Set producer timing delays
            if Timing_Delay_Str in args[endpoint]:
                timing_delays[endpoint] = args[endpoint][Timing_Delay_Str]
            # Set custom dictionaries
            if self._custom_dictionaries.name in args[endpoint]:
                custom_dicts[endpoint] = args[endpoint][self._custom_dictionaries.name]
            # Set create once list
            if self._create_once_endpoints.name in args[endpoint]:
                _verify_type('Create once count', int, args[endpoint][self._create_once_endpoints.name])
                if args[endpoint][self._create_once_endpoints.name] > 0:
                    create_once_endpoints.append(endpoint)

        self._resource_producer_timing_delays.set_val(timing_delays)
        self._custom_dictionaries.set_val(custom_dicts)
        self._create_once_endpoints.set_val(create_once_endpoints)

    def set_hostname(self, hostname):
        """ Sets the hostname

        @param hostname: The hostname to set
        @type  hostname: Str
        @return: None
        @rtype : None

        """
        self._host.val = hostname

    def set_port(self, port):
        """ Sets the port

        @param port: The port to set
        @type  port: Int
        @return: None
        @rtype : None

        """
        self._target_port.val = int(port)
        self._connection_settings.target_port = int(port)

    def in_smoke_test_mode(self) -> bool:
        """ Returns whether or not we are running a smoke test

        @return: True if we are running a smoke test

        """
        return self._fuzzing_mode.val == 'directed-smoke-test'

    def get_endpoint_custom_mutations_paths(self) -> dict:
        """ Returns the dict containing the endpoint specific custom mutations

        @return: The endpoint specific custom mutations dict

        """
        return self._custom_dictionaries.val

    def get_max_async_resource_creation_time(self, request_id):
        """ Gets the max async resource creation time for a specified request

        @param request_id: The ID of the request whose max async resource creation
                           time will be returned
        @type  requeset_id: Int

        @return: Max async resource creation time (seconds) for the specified request
        @rtype : Int
        """
        if self.wait_for_async_resource_creation:
            return max(self.get_producer_timing_delay(request_id),
                       self.max_async_resource_creation_time)
        return 0

    def get_producer_timing_delay(self, request_id):
        """ Gets the producer timing delay for a specified request

        @param request_id: The ID of the request whose producer timing
                            delay will be returned
        @type  request_id: Int

        @return: Producer timing delay for the specified request
        @rtype : Int

        """
        if request_id in self._resource_producer_timing_delays:
            return self._resource_producer_timing_delays[request_id]

        # No timing delay was set for this specific resource, so return
        # the global timing delay
        return self._global_producer_timing_delay.val

    def get_checker_arg(self, checker_name, arg):
        """ Returns a specified arg for a specified checker

        @param checker_name: The checker whose arg will be returned
        @type  checker_name: Str
        @param arg: The arg whose value will be returned
        @type  arg: Str

        @return: The specified arg for the specified checker (or None)
        @rtype : Varies

        """
        checker_name = checker_name.lower()
        try:
            if checker_name in self._checker_args and arg in self._checker_args[checker_name]:
                return self._checker_args.val[checker_name][arg]
            return None
        except:
            return None

    def validate_options(self):
        """ Verifies all required options exist

        Raises OptionValidationError if any validation fails.

        """
        if self.fuzzing_mode == 'random-walk' and self.max_sequence_length != 100:
            raise OptionValidationError("Should not provide maximum sequence length"
                                        " for random walk method")
        if self.token_refresh_interval and not self.token_refresh_cmd:
            raise OptionValidationError("Must specify command to refresh token")
        if self.token_refresh_cmd and not self.token_refresh_interval:
            raise OptionValidationError("Must specify refresh period in seconds")
        if self.request_throttle_ms and self.fuzzing_jobs != 1:
            raise OptionValidationError("Request throttling not available for multiple fuzzing jobs")
        if self.custom_bug_codes and self.custom_non_bug_codes:
            raise OptionValidationError("Both custom_bug_codes and custom_non_bug_codes lists were specified. "
                                        "Specifying both lists is not allowed.")
