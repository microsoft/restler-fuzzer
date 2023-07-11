# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Helpers for logging. """
from __future__ import print_function
import os
import sys
import shutil
import threading
import time
import statistics
import json
import types
import copy
import itertools
import datetime
from collections import OrderedDict
from shutil import copyfile
from collections import namedtuple

import engine.primitives as primitives
import engine.dependencies as dependencies
from restler_settings import Settings

import utils.formatting as formatting

PREPROCESSING_GENERATION = -1
POSTPROCESSING_GENERATION = -2

SETTINGS_NO_TOKENS_IN_LOGS = False
SETTINGS_SAVE_RESULTS_IN_FIXED_DIRNAME = False

# Experiment dir containing all logs
EXPERIMENT_DIR = None
# checkpoints destination
CKPT_DIR = None
# low level HTTP traffic logs
NETWORK_LOGS = None
# testcase buckets for tests that trigger errors
BUG_BUCKET_LOGS = None
# Extensive logging / experiment snapshots; mainly for paper
TIME_MACHINE = None
# Plots; mainly for paper
PLOTS_DIR = None
# fuzzing driver logs
MAIN_LOGS = None
# Request rendering logs.
REQUEST_RENDERING_LOGS = None
# GC tests logs.
GARBAGE_COLLECTOR_LOGS = None
# Experiment logs dir
LOGS_DIR = None
# Directory for bug bucket logs
BUG_BUCKETS_DIR = None
DELIM = "\r\n\r\n"

# This is the symbol that will appear before any request in a bug bucket
# log that should be sent as part of the replay.
REPLAY_REQUEST_INDICATOR = '-> '

# This symbol indicates additional information tied to a request in the bug
# bucket log to be used when replaying logs
BUG_LOG_NOTIFICATION_ICON = '! '

# Collection of NetworkLog objects identified by their thread ID
Network_Logs = dict()

LOG_TYPE_TESTING = 'testing'
LOG_TYPE_GC = 'gc'
LOG_TYPE_PREPROCESSING = 'preprocessing'
LOG_TYPE_REPLAY = 'replay'
LOG_TYPE_AUTH = 'auth'

class Bug():
     def __init__(self):

       self.filepath = None
       self.reproducible = False
       self.checker_name = None
       self.error_code = None

     def toJson(self):
        return json.dumps(self, default=lambda o : o.__dict__, indent=4)

class BugDetail():
    def __init__(self):

       self.status_code = 0
       self.checker_name = None
       self.reproducible = False
       self.verb = None
       self.endpoint = None
       self.status_text = None
       self.request_sequence = []

    def toJson(self):
        return json.dumps(self, default=lambda o : o.__dict__, indent=4)

class BugRequest():
    def __init__(self):

        self.producer_timing_delay = 0
        self.max_async_wait_time = 0
        self.replay_request = None
        self.response =None


Network_Auth_Log = None

class NetworkLog(object):
    """ Implements logic for creating, chunking, and writing to network logs """
    _MaxLogSize = 1024*1024*100 # = 100MB
    def __init__(self, log_name, thread_id):
        """ NetworkLog constructor

        @param thread_id: The thread ID of the thread writing to this log
        @type  thread_id: Int
        """
        self._current_log_num = 1
        self._thread_id = thread_id
        self._log_name = str(log_name)
        self._current_log_path = build_logfile_path(
            NETWORK_LOGS, self._log_name, self._thread_id, self._current_log_num)
        # create the first network logfile
        open(self._current_log_path, 'a').close

    def write(self, data):
        """ Writes to the current network log

        @param data: The data to write
        @type  data: Str

        @return: None
        @rtype : None

        """
        if Settings().disable_logging:
            return

        if os.path.getsize(self._current_log_path) > NetworkLog._MaxLogSize:
            # Create a new log if the current log has grown beyond the max size
            self._current_log_num += 1
            self._current_log_path = build_logfile_path(
                NETWORK_LOGS, self._log_name, self._thread_id, self._current_log_num)

        with open(self._current_log_path, 'a+', encoding='utf-8') as log_file:
            print(data, file=log_file)
            log_file.flush()
            os.fsync(log_file.fileno())

class SpecCoverageLog(object):
    __instance = None

    """ Implements logic for writing to the spec coverage file. """
    @staticmethod
    def Instance():
        """ Singleton's instance accessor

        @return SpecCoverageLog instance
        @rtype  SpecCoverageLog

        """
        if SpecCoverageLog.__instance == None:
            raise Exception("SpecCoverageLog not yet initialized.")
        return SpecCoverageLog.__instance

    def __init__(self):
        """ SpecCoverageLog constructor

        """
        if SpecCoverageLog.__instance:
            raise Exception("Attempting to create a new singleton instance.")

        self._renderings_logged = {}

        # create the spec coverage file
        file_path = os.path.join(LOGS_DIR, 'speccov-all-combinations.json')
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as file:
               file.write("{}")

        SpecCoverageLog.__instance = self

    def _get_request_coverage_summary_stats(self, rendered_request, req_hash, log_tracked_parameters=False,
                                            log_raw_requests=False):
        """ Constructs a json object with the coverage information for a request
        from the rendered request.  This info will be reported in a spec coverage file.

        @param rendered_request: The rendered request.
        @type  rendered_request: Request
        @param req_hash: The request hash
        @type  req_hash: Str

        @return: A dictionary containing a single entry with the key set to the request hash,
                 and the value to a dictionary with the coverage data.
        @rtype : Dict

        """
        from engine.core.requests import FailureInformation

        req=rendered_request
        coverage_data = {}
        coverage_data[req_hash] = {}
        req_spec = coverage_data[req_hash]
        req_spec['verb'] = req.method
        req_spec['endpoint'] = req.endpoint_no_dynamic_objects
        if req.stats.matching_prefix:
            matching_prefix = req.stats.matching_prefix
        else:
            matching_prefix = []

        if log_raw_requests:
            req_spec['valid'] = req.stats.valid
            req_spec['matching_prefix'] = matching_prefix

            if req.stats.sample_request:
                req_spec['request'] = req.stats.sample_request.request_str
                req_spec['response'] = req.stats.sample_request.response_str
            return coverage_data

        req_spec['verb_endpoint'] = f"{req.method} {req.endpoint_no_dynamic_objects}"
        req_spec['valid'] = req.stats.valid
        req_spec['matching_prefix'] = matching_prefix

        req_spec['invalid_due_to_sequence_failure'] = 0
        req_spec['invalid_due_to_resource_failure'] = 0
        req_spec['invalid_due_to_parser_failure'] = 0
        req_spec['invalid_due_to_500'] = 0
        if req.stats.failure == FailureInformation.SEQUENCE:
            req_spec['invalid_due_to_sequence_failure'] = 1
        elif req.stats.failure == FailureInformation.RESOURCE_CREATION:
            req_spec['invalid_due_to_resource_failure'] = 1
        elif req.stats.failure == FailureInformation.PARSER:
            req_spec['invalid_due_to_parser_failure'] = 1
        elif req.stats.failure == FailureInformation.BUG:
            req_spec['invalid_due_to_500'] = 1
        elif req.stats.failure == FailureInformation.MISSING_STATUS_CODE:
            req_spec['invalid_due_to_missing_response_code'] = 1
        req_spec['status_code'] = req.stats.status_code
        req_spec['status_text'] = req.stats.status_text
        req_spec['error_message'] = req.stats.error_msg
        req_spec['request_order'] = req.stats.request_order
        if req.stats.sample_request:
            req_spec['sample_request'] = copy.copy(vars(req.stats.sample_request))
            # Remove the raw request-response pair, as they are only logged when 'log_raw_requests' is true
            del req_spec['sample_request']['request_str']
            del req_spec['sample_request']['response_str']
        if req.stats.sequence_failure_sample_request:
            req_spec['sequence_failure_sample_request'] = copy.copy(vars(req.stats.sequence_failure_sample_request))
            del req_spec['sequence_failure_sample_request']['request_str']
            del req_spec['sequence_failure_sample_request']['response_str']
        if log_tracked_parameters:
            req_spec['tracked_parameters'] = {}
            for k, v in req.stats.tracked_parameters.items():
                req_spec['tracked_parameters'][k] = v

        return coverage_data

    def log_request_coverage_incremental(self, request=None, rendered_sequence=None, log_rendered_hash=True,
                                         log_raw_requests=True):
        """ Prints the coverage information for a request to the spec
        coverage file.
        If 'log_raw_requests' is set to 'True', prints an abbreviated summary of the coverage information
        that includes whether the request passed or failed and the request and response text.

        Pre-requisite: the file contains a json dictionary with
        zero or more elements.  The json object will be written into the
        top-level object.

        @param request: The request, for cases when a sequence could not be rendered due to dependency failures.
        @type  rendered_sequence: Request

        @param rendered_sequence: The rendered sequence
        @type  rendered_sequence: RenderedSequence

        @param log_rendered_hash: Log the hash including the rendered combination.
                                  If 'False', logs only the request hash.
        @type  log_raw_requests: Bool

        @param log_raw_requests: The rendered sequence
        @type  log_raw_requests: Bool

        @return: None
        @rtype : None

        """

        def write_incremental_coverage(file_path, req_coverage):
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write("{}")

            coverage_as_json = json.dumps(req_coverage, indent=4)
            # remove the start and end brackets, since they will already be present
            # also remove the end newline
            coverage_as_json = coverage_as_json[1:len(coverage_as_json) - 2]

            with open(file_path, 'r+', encoding='utf-8') as file:
                pos = file.seek(0, os.SEEK_END)
                file_size = file.tell()
                pos = file.seek(file_size - 1, 0)

                if file_size > 2:
                    file.write(",")
                file.write(coverage_as_json)
                file.write("}")

        if Settings().disable_logging:
            return

        from engine.core.requests import FailureInformation
        if rendered_sequence:
            req=rendered_sequence.sequence.last_request
        else:
            if not request:
                raise Exception("Either the rendered sequence or request must be specified.")
            req = request

        # For uniqueness, the rendered request hash should include
        # the current combination IDs of every request in the sequence.
        if log_rendered_hash and rendered_sequence:
            req_hash = f"{req.method_endpoint_hex_definition}_{str(req._current_combination_id)}"
            if rendered_sequence.sequence.prefix.length > 0:
                req_hash=f"{req_hash}__{rendered_sequence.sequence.prefix_combination_id}"
        else:
            req_hash = req.method_endpoint_hex_definition

        if req_hash in self._renderings_logged:
            # Duplicate spec coverage should not be logged.
            raise Exception(f"ERROR: spec coverage is being logged twice for the same rendering: {req_hash}.")

        req_coverage = self._get_request_coverage_summary_stats(req, req_hash, log_tracked_parameters=log_rendered_hash)
        self._renderings_logged[req_hash] = req_coverage[req_hash]['valid']

        file_path = os.path.join(LOGS_DIR, 'speccov-all-combinations.json')
        write_incremental_coverage(file_path, req_coverage)

        req_coverage = self._get_request_coverage_summary_stats(req, req_hash, log_tracked_parameters=log_rendered_hash,
                                                                log_raw_requests=True)
        file_path = os.path.join(LOGS_DIR, 'speccov-min.json')
        write_incremental_coverage(file_path, req_coverage)

    def generate_summary_speccov(self):
        """ Generate a speccov file that contains one entry for each request, which contains whether the request
            is valid and a sample request.
        """
        file_path = os.path.join(LOGS_DIR, 'speccov-all-combinations.json')
        new_file_path = os.path.join(LOGS_DIR, 'speccov.json')

        if Settings().fuzzing_mode == 'test-all-combinations':
            shutil.copyfile(file_path, new_file_path)
            return
            # The speccov file has the same content as speccov-all-combinations.  Simply copy it.

        try:
            full_speccov = json.load(open(file_path, encoding='utf-8'))
        except Exception as error:
            print(f"Cannot load {file_path}: {error!s}.")
            sys.exit(-1)

        def get_verb_endpoint(item):
            (k, v) = item
            return v['verb_endpoint']

        def is_valid(item):
            (k, v) = item
            return v['valid']

        new_speccov = {}
        for key, group in itertools.groupby(full_speccov.items(), get_verb_endpoint):
            req_type_results = [x for x in group]

            valid_results = list(filter(is_valid, req_type_results))
            if len(valid_results) > 0:
                (k, v) = valid_results[0]
            else:
                # Record the first result in the spec coverage file
                # This is helpful when example payloads are used, since they are attempted first
                (k, v) = req_type_results[0]
            new_speccov[k] = v

        json.dump(new_speccov, open(new_file_path, 'w', encoding='utf-8'), indent=4)

def no_tokens_in_logs():
    """ Do not print token data in logs
    @return: None
    @rtype: None
    """
    global SETTINGS_NO_TOKENS_IN_LOGS
    SETTINGS_NO_TOKENS_IN_LOGS = True
    return

def save_results_in_fixed_dirname():
    """ Save results in a directory with a fixed name
    @ return: None
    @rtype: None
    """
    global SETTINGS_SAVE_RESULTS_IN_FIXED_DIRNAME
    SETTINGS_SAVE_RESULTS_IN_FIXED_DIRNAME = True
    return

def create_experiment_dir():
    """ creates the unique EXPERIMENT_DIR directory where results are saved
    @return: None
    @rtype: None
    """
    global EXPERIMENT_DIR
    global SETTINGS_SAVE_RESULTS_IN_FIXED_DIRNAME
    if SETTINGS_SAVE_RESULTS_IN_FIXED_DIRNAME:
        EXPERIMENT_DIR = os.path.join(os.getcwd(), 'RestlerResults')
    else:
        adder = 0
        while True:
            EXPERIMENT_DIR = os.path.join(os.getcwd(), 'RestlerResults', f'experiment{(os.getpid() + adder)!s}')
            if not os.path.isdir(EXPERIMENT_DIR):
                break
            adder += 1

    global CKPT_DIR
    CKPT_DIR = os.path.join(EXPERIMENT_DIR, 'checkpoints')
    global BUG_BUCKETS_DIR
    BUG_BUCKETS_DIR = os.path.join(EXPERIMENT_DIR, 'bug_buckets')
    global LOGS_DIR
    LOGS_DIR = os.path.join(EXPERIMENT_DIR, 'logs')
    global NETWORK_LOGS
    NETWORK_LOGS = os.path.join(LOGS_DIR, 'network.txt')
    global BUG_BUCKET_LOGS
    BUG_BUCKET_LOGS = os.path.join(BUG_BUCKETS_DIR, 'bug_buckets.txt')
    global TIME_MACHINE
    TIME_MACHINE = os.path.join(EXPERIMENT_DIR, 'time_machine')
    global PLOTS_DIR
    PLOTS_DIR = os.path.join(EXPERIMENT_DIR, 'plots')
    global MAIN_LOGS
    MAIN_LOGS = os.path.join(LOGS_DIR, 'main.txt')
    global REQUEST_RENDERING_LOGS
    REQUEST_RENDERING_LOGS = os.path.join(LOGS_DIR, 'request_rendering.txt')
    global GARBAGE_COLLECTOR_LOGS
    GARBAGE_COLLECTOR_LOGS = os.path.join(LOGS_DIR, 'garbage_collector.txt')

    os.makedirs(LOGS_DIR)

def build_logfile_path(logname, logType, threadId, log_num=1):
    """ Helper to create a logfile path incorporating the thread ID in the filename before the file type suffix.

    @param logname: The valid base path without the thread Id.
    @type  logname: Str
    @param logType: The type of log (e.g. fuzzing)
    @type  logType: Str
    @param threadId:  The thread id to be inserted into the path.
    @type  threadId: Int
    @param log_num: The current log number of this type. Used when chunking logs
    @type  log_num: Int

    @return: Formatted logfile path
    @rtype : Str

    """
    typeStart = logname.rfind(".txt")
    return f"{logname[:typeStart]}.{logType}.{threadId!s}.{log_num!s}{logname[typeStart:]}"

def remove_tokens_from_logs(data):
    """ If the no-tokens-in-logs setting is set, this function will attempt to
    find the token in the data string and replace it with _OMITTED_AUTH_TOKEN_
    @type  data: Str

    @return: The data with the token removed
    @rtype : Str

    """
    global SETTINGS_NO_TOKENS_IN_LOGS
    from engine.core.request_utilities import replace_auth_token
    if SETTINGS_NO_TOKENS_IN_LOGS:
        data = replace_auth_token(data, '_OMITTED_AUTH_TOKEN_')
    return data

def garbage_collector_logging(msg):
    """ Helper to log garbage collection stats.

    @param msg: The message to log.
    @type  msg: Str

    @return: None
    @rtype : None

    """
    thread_id = threading.current_thread().ident
    filename = build_logfile_path(GARBAGE_COLLECTOR_LOGS, LOG_TYPE_GC, str(thread_id))
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError:
            pass
    with open(filename, "a+", encoding='utf-8') as log_file:
        print(msg, file=log_file)

main_lock = threading.Semaphore(1)
def write_to_main(data: str, print_to_console: bool=False):
    """ Writes to the main log

    @param data: The data to write
    @param print_to_console: If true, print to console as well as log

    @return: None

    """
    if Settings().disable_logging:
        return
    try:
        main_lock.acquire()
        with open(MAIN_LOGS, "a+", encoding='utf-8') as f:
            print(data, file=f)
            f.flush()
    except Exception as err:
        print(f"Exception writing to main log: {err!s}")
    finally:
        main_lock.release()

    if print_to_console:
        print(data)

def create_network_log(log_name):
    """ Creates a new network log type

    @param log_name: The name of the log - will be included in filename
    @type  log_name: Str

    @return: None
    @rtype : None

    """
    thread_id = threading.current_thread().ident
    if thread_id not in Network_Logs:
        Network_Logs[thread_id] = NetworkLog(log_name, thread_id)
    else:
        raise Exception(f"Network log with thread id {thread_id} already exists.")

def raw_network_logging(data):
    """ Helper to log network traffic transfered over sockets.

    @param data: The data paylod to be logged.
    @type data: Str

    @return: None
    @rtype : None

    """
    if data is None:
        # This case may occur when converting the response payload does not have a string
        # representation.  As a workaround, print text to the log so that it contains
        # a received response.
        data = '_OMITTED_UNKNOWN_DATA_'

    # To make sure binary data are not flushed out in the logs we drop anything
    # around CUSTOM_BOUNDARY, which is the binary payload
    if ('octet-stream' in data) and ('_CUSTOM_BOUNDARY_' in data):
        data = data.split('_CUSTOM_BOUNDARY_')
        data = data[0] + '_OMITTED_BINARY_DATA_' + data[-1]

    # remove tokens from the logs
    data = remove_tokens_from_logs(data)

    thread_id = threading.current_thread().ident
    if thread_id not in Network_Logs:
        raise Exception(f"Network log with thread id {thread_id} does not exist.")

    network_log = Network_Logs[thread_id]
    network_log.write(f"{formatting.timestamp()}: {data}")

def auth_logging(data):
    global Network_Auth_Log
    if Network_Auth_Log is None:
        thread_id = threading.current_thread().ident
        Network_Auth_Log = NetworkLog(LOG_TYPE_AUTH, thread_id)
    Network_Auth_Log.write(f"{formatting.timestamp()}: {data}")

def custom_network_logging(sequence, candidate_values_pool, **kwargs):
    """ Helper to log (in a more civilized manner) the template of the request
    which will be subsequently rendered with the respective feasible value
    combinations.

    @param sequence: The sequence to be logged.
    @type  sequence: Sequence class object.
    @param candidate_values_pool: the pool of values for primitive types.
    @type candidate_values_pool: Dict

    @return: None
    @rtype : None

    """
    thread_id = threading.current_thread().ident
    if thread_id not in Network_Logs:
        Network_Logs[thread_id] = NetworkLog(LOG_TYPE_TESTING, thread_id)

    network_log = Network_Logs[thread_id]

    if bool(kwargs):
        for key in kwargs:
            network_log.write(f"{key}: {kwargs[key]}")

    network_log.write(f"\nGeneration-{len(sequence.requests)}: Rendering Sequence-{sequence.seq_i + 1}")
    for req_i, request in enumerate(sequence.requests):

        definition = request.definition
        if len(definition) == 0:
            return
        if req_i + 1  == len(sequence.requests):
            remaining = request.num_combinations(candidate_values_pool)\
                - request._current_combination_id
            network_log.write(f"\n\tRequest: {req_i + 1} (Remaining candidate combinations: {remaining})")
            network_log.write(f"\tRequest hash: {request.method_endpoint_hex_definition}\n")
        else:
            network_log.write(f"\n\tRequest: {req_i + 1}"
                              " (Current combination: "
                              f"{request._current_combination_id} / {request.num_combinations(candidate_values_pool)})")

        print_data = get_rendering_stats_definition(request, candidate_values_pool)
        network_log.write(print_data)
    network_log.write("")

BugTuple = namedtuple('BugTuple', ['filename_of_replay_log', 'bug_hash', 'reproduce_attempts', 'reproduce_successes'])
# Dict to track whether or not a bug was already logged:
#   {"{seq_hash}_{bucket_class}": BugTuple()}
Bugs_Logged = dict()
# Dict of bug hashes to be printed to bug_buckets.json
#   {bug_hash: {"file_path": replay_log_relative_path}}
Bug_Hashes = dict()

def update_bug_buckets(bug_buckets, bug_request_data, bug_hash, additional_log_str=None):
    """
    @param bug_buckets: Dictionary containing bug bucket information
    @type  bug_buckets: Dict
    @param bug_request_data: The list of request data that was sent to create the bug
    @type  bug_request_data: List[SentRequestData]
    @param bug_hash: The unique hash for this bug
    @type  bug_hash: Str
    @param additional_log_str: An optional string that can be added to the bug's replay header
    @type  additional_log_str: Str

    @return: None
    @rtype : None

    """
    Header_Len = 80
    def get_bug_filename(file_extension):
        return f"{bucket_class}_{len(bug_buckets[bucket_class].keys())}.{file_extension}"

    def log_new_bug():
        # Create the new bug log
        filename = get_bug_filename("replay.txt")
        filepath = os.path.join(BUG_BUCKETS_DIR, filename)

        with open(filepath, "w+", encoding='utf-8') as bug_file:
            # Print the header
            print(f"{'#' * Header_Len}", file=bug_file)
            print(f" {name_header}\n", file=bug_file)
            if additional_log_str is not None:
                print(f" {additional_log_str}\n", file=bug_file)
            print(f" Hash: {bug_hash}\n", file=bug_file)
            print(" To attempt to reproduce this bug using restler, run restler with the command", file=bug_file)
            print(" line option of --replay_log <path_to_this_log>.", file=bug_file)
            print(" If an authentication token is required, you must also specify the token_refresh_cmd.", file=bug_file)
            print("\n This log may contain specific values for IDs or names that were generated", file=bug_file)
            print(" during fuzzing, using the fuzzing dictionary. Such names will be re-played", file=bug_file)
            print(" without modification. You must update the replay log manually with any changes", file=bug_file)
            print(" required to execute the requests in your environment (for example, replacing", file=bug_file)
            print(" pre-created account, subscription, or other resource IDs, as needed).", file=bug_file)
            print(f"{'#' * Header_Len}\n", file=bug_file)

            # Print each of the sent requests
            for req in bug_request_data:
                data = repr(req.rendered_data).strip("'")
                print(f'{REPLAY_REQUEST_INDICATOR}{data}', file=bug_file)
                print(f"{BUG_LOG_NOTIFICATION_ICON}producer_timing_delay {req.producer_timing_delay}", file=bug_file)
                print(f"{BUG_LOG_NOTIFICATION_ICON}max_async_wait_time {req.max_async_wait_time}", file=bug_file)
                print(f"PREVIOUS RESPONSE: {req.response!r}\n", file=bug_file)

            log_file.flush()
            os.fsync(log_file.fileno())

            return filename

    def log_new_bug_as_json():
        # Create the new bug log in json format
        filename = get_bug_filename("json")
        filepath = os.path.join(BUG_BUCKETS_DIR, filename)
        currentsequence = bug_bucket.sequence

        bugDetail = BugDetail()
        bugDetail.checker_name = bug_bucket.origin
        bugDetail.reproducible = bug_bucket.reproducible
        bugDetail.endpoint = currentsequence.last_request._endpoint_no_dynamic_objects
        bugDetail.verb = currentsequence.last_request.method
        sequence_request_counter = 0
        for req in bug_request_data:
            try:
                bugRequest = BugRequest()
                bugRequest.replay_request = req.rendered_data
                bugRequest.response = req.response
                bugRequest.producer_timing_delay = req.producer_timing_delay
                bugRequest.max_async_wait_time = req.max_async_wait_time
                bugDetail.request_sequence.append(bugRequest)
                if sequence_request_counter == len(bug_request_data) - 1:
                    if len(req.response.split(DELIM)) > 1:
                        split_responsebody = req.response.split(DELIM)
                        response_headers = split_responsebody[0].split("\r\n")
                        response_status_code_and_status_message = response_headers[0].split(" ")
                        bugDetail.status_code = response_status_code_and_status_message[1]
                        bugDetail.status_text = ' '.join(response_status_code_and_status_message[2:])
                    else :
                        bugDetail.status_code = ''
                        bugDetail.status_text = ''

                sequence_request_counter = sequence_request_counter + 1
            except Exception as error:
                write_to_main(f"Failed to write bug bucket as json log: {error!s}")
                filename = 'Failed to create bug bucket as json log.'

        jsonString = bugDetail.toJson()
        with open(filepath, "w+", encoding='utf-8') as bug_file:
            print(f'{jsonString}', file=bug_file)
            log_file.flush()
            os.fsync(log_file.fileno())

        return filename

    def write_incremental_bugs(file_path, req_bug):
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write("{\"bugs\":[]}")

        req_bug_as_json = req_bug.toJson() # json.dumps(req_bug, indent=4)
        # remove the start and end brackets, since they will already be present
        # also remove the end newline
        req_bug_as_json = req_bug_as_json[0:len(req_bug_as_json) - 2]

        with open(file_path, 'r+', encoding='utf-8') as file:
            pos = file.seek(0, os.SEEK_END)
            file_size = file.tell()
            pos = file.seek(file_size - 2, 0)

            if file_size > 11:
                file.write(",")
            file.write(req_bug_as_json)
            file.write("}]}")

    def add_hash(replay_filename):
        """ Helper that adds bug hash to the bug buckets json file """
        global Bug_Hashes
        Bug_Hashes[bug_hash] = {"file_path": replay_filename}
        with open(os.path.join(BUG_BUCKETS_DIR, "bug_buckets.json"), "w+", encoding='utf-8') as hash_json:
            json.dump(Bug_Hashes, hash_json, indent=4)

    thread_id = threading.current_thread().ident
    # Create the bug_buckets directory if it doesn't yet exist
    if not os.path.exists(BUG_BUCKETS_DIR):
        os.makedirs(BUG_BUCKETS_DIR)

    filename = BUG_BUCKET_LOGS
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError:
            pass

    global Bugs_Logged
    with open(filename, "w+", encoding='utf-8') as log_file:
        tot_count = 0
        for bucket_class in bug_buckets:
            print(f"{bucket_class}: {len(bug_buckets[bucket_class].keys())}", file=log_file)
            tot_count += len(bug_buckets[bucket_class].keys())
        print(f"Total Buckets: {tot_count}", file=log_file)
        print("-------------", file=log_file)
        for bucket_class in bug_buckets:
            for seq_hash in bug_buckets[bucket_class]:
                bug_bucket = bug_buckets[bucket_class][seq_hash]
                bucket_hash = f"{seq_hash}_{bucket_class}"
                name_header = bucket_class
                if bucket_hash not in Bugs_Logged:
                    try:
                        filename = log_new_bug()
                        filenameJson = log_new_bug_as_json()
                        requestBug = Bug()
                        requestBug.filepath = filenameJson
                        requestBug.reproducible = bug_bucket.reproducible
                        requestBug.checker_name = bug_bucket.origin
                        requestBug.error_code = bug_bucket.error_code

                        write_incremental_bugs(os.path.join(BUG_BUCKETS_DIR, "Bugs.json"),requestBug)
                        Bugs_Logged[bucket_hash] = BugTuple(filename, bug_hash, bug_bucket.reproduce_attempts, bug_bucket.reproduce_successes)
                        add_hash(filename)
                    except Exception as error:
                        write_to_main(f"Failed to write bug bucket log: {error!s}")
                        filename = 'Failed to create replay log.'
                else:
                    filename = Bugs_Logged[bucket_hash].filename_of_replay_log
                    this_bug_hash = Bugs_Logged[bucket_hash].bug_hash
                    Bugs_Logged[bucket_hash] = BugTuple(filename, this_bug_hash, bug_bucket.reproduce_attempts, bug_bucket.reproduce_successes)

                if bug_bucket.reproducible:
                    print(f'{name_header} - Bug was reproduced - {filename}', file=log_file)
                else:
                    print(f'{name_header} - Unable to reproduce bug - {filename}', file=log_file)
                    print(f'Attempted to reproduce {Bugs_Logged[bucket_hash].reproduce_attempts} time(s); '
                          f'Reproduced {Bugs_Logged[bucket_hash].reproduce_successes} time(s)', file=log_file)
                print(f"Hash: {Bugs_Logged[bucket_hash].bug_hash}", file=log_file)
                for request in bug_bucket.sequence:
                    for payload in list(map(lambda x: x[1], request.definition)):
                        print(repr(payload)[1:-1], end='', file=log_file)
                    print(file=log_file)
                print("-" * Header_Len, file=log_file)

        log_file.flush()
        os.fsync(log_file.fileno())

def copy_stats(counter):
    """

    @param counter: Increment over time (every ten minutes) of logging.
    @type  counter: Int

    @return: None
    @rtype : None

    """
    return

    if not os.path.exists(TIME_MACHINE):
        try:
            os.makedirs(TIME_MACHINE)
        except OSError:
            print(f"Exception Cannot Create: {TIME_MACHINE}")
    try:
        thread_id = threading.current_thread().ident

        coverage = "/home/git/gitlab/scripts/coverage_stats.txt"
        copyfile(coverage, os.path.join(TIME_MACHINE, f"coverage_stats{counter}.txt"))

        if not os.path.exists(PLOTS_DIR):
            os.makedirs(PLOTS_DIR)
        clientside = os.path.join(PLOTS_DIR, "clientside.csv")
        copyfile(clientside, os.path.join(TIME_MACHINE, f"clientside{counter}.csv"))

        serverside = os.path.join(PLOTS_DIR, "serverside.csv")
        copyfile(serverside, os.path.join(TIME_MACHINE, f"serverside{counter}.csv"))

        networklogs = build_logfile_path(NETWORK_LOGS, LOG_TYPE_TESTING, str(threading.current_thread().ident))
        copyfile(networklogs,
                 os.path.join(TIME_MACHINE, f"{os.path.basename(networklogs)}.{counter}"))

        try:
            testcaseslogs = f'{BUG_BUCKET_LOGS}.{thread_id!s}'
            copyfile(testcaseslogs,
                     os.path.join(TIME_MACHINE, f"{os.path.basename(testcaseslogs)}.{counter}"))
        except Exception:
            pass

    except Exception as error:
        print("Exception copying:", error)

def print_async_results(req_data, message):
    """ Prints the results of an async resource creation

    @param req_data: The request data that was sent
    @type  req_data: Str
    @param message: The message to print
    @type  message: Str

    @return: None
    @rtype : None

    """
    ASYNC_LOG = os.path.join(LOGS_DIR, "async_log.txt")

    req_data = remove_tokens_from_logs(req_data)

    with open(ASYNC_LOG, "a+", encoding='utf-8') as f:
        print(repr(req_data), file=f)
        print(f"{message}\n", file=f)

def print_req_collection_stats(req_collection, candidate_values_pool):
    """  Prints request collection evolution stats.

    @param req_collection: A collection of requests.
    @type  req_collection: FuzzingRequestCollection class object.
    @param candidate_values_pool: The shared global pool of candidate values
    @type  candidate_values_pool: CandidateValuesPool

    @return: None
    @rtype : None

    """
    timestamp = formatting.timestamp()
    data = f"{timestamp}: Going to fuzz a set with {req_collection.size} requests\n"

    for i, r in enumerate(req_collection):
        val = r.num_combinations(candidate_values_pool)
        data += f"{timestamp}: Request-{i}: Value Combinations: {val}\n"

    val = statistics.mean([r.num_combinations(candidate_values_pool)\
                   for r in req_collection])
    data += f"{timestamp}: Avg. Value Combinations per Request: {val}\n"

    val = statistics.median([r.num_combinations(candidate_values_pool)\
                     for r in req_collection])
    data += f"{timestamp}: Median Value Combinations per Request: {val}\n"

    val = min([r.num_combinations(candidate_values_pool)\
                  for r in req_collection])
    data += f"{timestamp}: Min Value Combinations per Request: {val}\n"

    val = max([r.num_combinations(candidate_values_pool)\
                  for r in req_collection])
    data += f"{timestamp}: Max Value Combinations per Request: {val}\n"

    val = 0
    for r in req_collection:
        val += len(r.produces)
        val += len(r.consumes)
    data += f"{timestamp}: Total dependencies: {val}\n"

    write_to_main(data)

def print_memory_consumption(req_collection, fuzzing_monitor, fuzzing_mode, generation):
    """ Prints global generation's memory consumption statistics.

    @param req_collection: The requests collection.
    @type  req_collection: RequestCollection class object.
    @param fuzzing_monitor: The global fuzzing monitor
    @type  fuzzing_monitor: FuzzingMonitor
    @param fuzzing_mode: The current fuzzing mode
    @type  fuzzing_mode: Str
    @param generation: The current sequence generation
    @type  generation: Int

    @return: None
    @rtype : None

    """
    from engine.bug_bucketing import BugBuckets
    timestamp = formatting.timestamp()
    print_memory_consumption.invocations += 1

    lcov = 0

    avg_val = statistics.mean([r.num_combinations(req_collection.candidate_values_pool)\
                   for r in req_collection])
    write_to_main(
        f"MARKER, {print_memory_consumption.invocations}, "
        f"{os.path.basename(req_collection._grammar_name)[:-3]}, "
        f"{req_collection.size}, {avg_val}, {fuzzing_mode}, "
        f"{timestamp}, {lcov}, {generation}, "
        f"{fuzzing_monitor.num_requests_sent()['main_driver']}"

        f"{timestamp}: Total Creations of Dyn Objects: {dependencies.object_creations}\n"
        f"{timestamp}: Total Accesses of Dyn Objects: {dependencies.object_accesses}\n"
        f"{timestamp}: Total Requests Sent: {fuzzing_monitor.num_requests_sent()}\n"
        f"{timestamp}: Bug Buckets: {BugBuckets.Instance().num_bug_buckets()}\n"
    )

print_memory_consumption.invocations = 0


def print_generation_stats(req_collection, fuzzing_monitor, global_lock, final=False):
    """ Prints global generation's statistics.

    @param req_collection: The requests collection.
    @type  req_collection: RequestCollection class object.
    @param fuzzing_monitor: The global fuzzing monitor
    @type  fuzzing_monitor: FuzzingMonitor
    @param global_lock: Lock object used for sync of more than one fuzzing jobs.
    @type  global_lock: thread.Lock object
    @param final: If set to True, this is the end of the run generation stats
    @type  final: Bool

    @return: None
    @rtype : None

    """
    from engine.bug_bucketing import BugBuckets
    from engine.transport_layer.response import VALID_CODES
    from engine.transport_layer.response import RESTLER_INVALID_CODE
    timestamp = formatting.timestamp()

    successful_requests = []
    num_fully_valid = 0
    num_sequence_failures = 0
    for r in req_collection:
        query_result = fuzzing_monitor.query_status_codes_monitor(r, VALID_CODES, [RESTLER_INVALID_CODE], global_lock)
        successful_requests.append(query_result.valid_code)
        if(query_result.fully_valid):
            num_fully_valid += 1
        if(query_result.sequence_failure):
            num_sequence_failures += 1

    sum_successful_requests = sum(successful_requests)
    num_rendered_requests = fuzzing_monitor.num_fully_rendered_requests(req_collection, global_lock)

    final_spec_coverage = f"{num_fully_valid} / {req_collection.size}"
    rendered_requests = f"{num_rendered_requests} / {req_collection.size}"
    rendered_requests_valid_status = f"{sum_successful_requests} / {num_rendered_requests}"
    num_invalid_by_failed_resource_creations = sum_successful_requests - num_fully_valid
    total_object_creations = dependencies.object_creations
    total_requests_sent = fuzzing_monitor.num_requests_sent()
    bug_buckets = BugBuckets.Instance().num_bug_buckets()

    write_to_main(
        f"{timestamp}: Final Swagger spec coverage: {final_spec_coverage}\n"
        f"{timestamp}: Rendered requests: {rendered_requests}\n"
        f"{timestamp}: Rendered requests with \"valid\" status codes: {rendered_requests_valid_status}\n"
        f"{timestamp}: Num fully valid requests (no resource creation failures): {num_fully_valid}\n"
        f"{timestamp}: Num requests not rendered due to invalid sequence re-renders: {num_sequence_failures}\n"
        f"{timestamp}: Num invalid requests caused by failed resource creations: {num_invalid_by_failed_resource_creations}\n"
        f"{timestamp}: Total Creations of Dyn Objects: {total_object_creations}\n"
        f"{timestamp}: Total Requests Sent: {total_requests_sent}\n"
        f"{timestamp}: Bug Buckets: {BugBuckets.Instance().num_bug_buckets()}"
    )

    if final:
        testing_summary = OrderedDict()
        testing_summary['final_spec_coverage'] = final_spec_coverage
        testing_summary['rendered_requests'] = rendered_requests
        testing_summary['rendered_requests_valid_status'] = rendered_requests_valid_status
        testing_summary['num_fully_valid'] = num_fully_valid
        testing_summary['num_sequence_failures'] = num_sequence_failures
        testing_summary['num_invalid_by_failed_resource_creations'] = num_invalid_by_failed_resource_creations
        testing_summary['total_object_creations'] = total_object_creations
        testing_summary['total_requests_sent'] = total_requests_sent
        testing_summary['bug_buckets'] = bug_buckets
        testing_summary['reproducible_bug_buckets'] = BugBuckets.Instance().repro_bug_buckets()
        settings_summary = OrderedDict()
        settings_summary['random_seed'] = Settings().random_seed
        testing_summary['settings'] = settings_summary
        with open(os.path.join(LOGS_DIR, "testing_summary.json"), "w+", encoding='utf-8') as summary_json:
            json.dump(testing_summary, summary_json, indent=4)


def print_gc_summary(garbage_collector):
    """ Prints the summary of garbage collection statistics.
    """
    gc_summary = OrderedDict()
    gc_summary['delete_stats'] = garbage_collector.gc_stats
    with open(os.path.join(LOGS_DIR, "gc_summary.json"), "w+", encoding='utf-8') as summary_json:
        json.dump(gc_summary, summary_json, indent=4)


def format_request_block(request_id, request_block, candidate_values_pool):
    primitive = request_block[0]
    if primitive == primitives.FUZZABLE_GROUP:
        field_name = request_block[1]
        default_val = request_block[2]
        quoted = request_block[3]
        examples = request_block[4]
    elif primitive in [ primitives.CUSTOM_PAYLOAD,
                        primitives.CUSTOM_PAYLOAD_HEADER,
                        primitives.CUSTOM_PAYLOAD_QUERY,
                        primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX ]:
        default_val = None
        field_name = request_block[1]
        quoted = request_block[2]
        examples = request_block[3]
    else:
        default_val = request_block[1]
        quoted = request_block[2]
        examples = request_block[3]
        field_name = request_block[4]

    # Handling dynamic primitives that need fresh rendering every time
    if primitive == "restler_fuzzable_uuid4":
        values = [primitives.restler_fuzzable_uuid4]
    # Handle enums that have a list of values instead of one default val
    elif primitive == "restler_fuzzable_group":
        values = list(default_val)
    # Handle multipart/formdata
    elif primitive == "restler_multipart_formdata":
        values = ['_OMITTED_BINARY_DATA_']
        default_val = '_OMITTED_BINARY_DATA_'
    # Handle custom payload
    elif primitive == "restler_custom_payload" or\
         primitive == "restler_custom_payload_header" or\
         primitive == "restler_custom_payload_query":
        current_fuzzable_tag = field_name
        values = candidate_values_pool.get_candidate_values(primitive, request_id=request_id, tag=current_fuzzable_tag, quoted=quoted)
        if not isinstance(values, list):
            values = [values]
        if len(values) == 1:
            default_val = values[0]
    # Handle custom payload with uuid4 suffix
    elif primitive == "restler_custom_payload_uuid4_suffix":
        current_fuzzable_tag = field_name
        values = candidate_values_pool.get_candidate_values(primitive, request_id=request_id, tag=current_fuzzable_tag, quoted=quoted)
        default_val = values[0]
    # Handle all the rest
    else:
        values = candidate_values_pool.get_fuzzable_values(primitive, default_val, request_id, quoted=quoted, examples=examples)
        if primitives.is_value_generator(values):
            values = [values]
    return primitive, values, default_val


def get_rendering_stats_definition(request, candidate_values_pool, log_file=None, log_all_fuzzable_values=False):
    print_values=[]

    for request_block in request.definition:
        primitive, values, default_val = format_request_block(request.request_id, request_block, candidate_values_pool)

        if isinstance(values, list) and len(values) > 1:
            print_val=values if log_all_fuzzable_values else f"[{values[0]}, {values[1]}, ...]"
            print_values.append(f"\t\t+ {primitive}: {print_val}")
        elif isinstance(default_val, list) and len(default_val) > 1:
            print_val=default_val if log_all_fuzzable_values else f"{default_val[0]}, {default_val[1]}, ...]"
            print_values.append(f"\t\t- {primitive}: {default_val[:3]}")
        else:
            print_val = values[0] if values else default_val
            print_values.append(f"\t\t- {primitive}: {print_val!r}")

    return "\n".join(print_values)

def format_rendering_stats_definition(request, candidate_values_pool, log_file=None, log_all_fuzzable_values=False):
    print_data = get_rendering_stats_definition(request, candidate_values_pool, log_file=log_file, log_all_fuzzable_values=log_all_fuzzable_values)

    if log_file:
        print(print_data, file=log_file)
        print("", file=log_file)
    else:
        write_to_main(print_data)
        write_to_main("")

def print_request_rendering_stats(candidate_values_pool, fuzzing_requests, fuzzing_monitor, num_rendered_requests, generation, global_lock):
    """ Prints to file statistics for request renderings.

    @param candidate_values_pool: The global pool of candidate values
    @type  candidate_values_pool: CandidateValuesPool
    @param fuzzing_requests: The collection of requests to be fuzzed.
    @type  fuzzing_requests: FuzzingRequestCollection class object.
    @param fuzzing_monitor: The global monitor of the fuzzing run
    @type  fuzzing_monitor: FuzzingMonitor
    @param num_rendered_requests: Number of requests that have been rendered
                                    at least once.
    @type  num_rendered_requests: Int
    @param generation: Current generation.
    @type  generation: Int
    @param global_lock: Lock object used for sync of more than one fuzzing jobs.
    @type  global_lock: thread.Lock object

    @return: None
    @rtype : None

    """
    from engine.transport_layer.response import VALID_CODES
    from engine.transport_layer.response import RESTLER_INVALID_CODE
    successful_requests = []
    fully_valid_count = 0
    for r in fuzzing_requests.all_requests:
        query_result = fuzzing_monitor.query_status_codes_monitor(r, VALID_CODES, [RESTLER_INVALID_CODE], global_lock)
        successful_requests.append(query_result.valid_code)
        if(query_result.fully_valid):
            fully_valid_count += 1

    timestamp = formatting.timestamp()

    if generation == PREPROCESSING_GENERATION:
        generation_name = "Preprocessing"
    elif generation == POSTPROCESSING_GENERATION:
        generation_name = "Postprocessing"
    else:
        generation_name = f"Generation-{generation}"

    with open(REQUEST_RENDERING_LOGS, "a+", encoding='utf-8') as log_file:
        print(f"\n{timestamp}: {generation_name}"\
              f"\n{timestamp}: \tRendered requests: {num_rendered_requests} / {fuzzing_requests.size_all_requests}"\
              f"\n{timestamp}: \tRendered requests with \"valid\" status codes: {sum(successful_requests)} / {num_rendered_requests}"\
              f"\n{timestamp}: \tRendered requests determined to be fully valid (no resource creation failures): {fully_valid_count} / {num_rendered_requests}", file=log_file)

        # if all request have succeded, we don't need longer generations
        if sum(successful_requests) == len(successful_requests):
            return

        print(f"{timestamp}: List of failing requests:", file=log_file)

        for ind, request in enumerate(fuzzing_requests):
            if successful_requests[ind]:
                continue
            if not fuzzing_monitor.is_fully_rendered_request(request,
                                                            global_lock):
                continue

            if len(request.definition) == 0:
                return

            print(f"\tRequest: {ind}", file=log_file)
            format_rendering_stats_definition(request, candidate_values_pool, log_file)

        print("-------------------------\n", file=log_file)
        log_file.flush()


def print_request_rendering_stats_never_rendered_requests(fuzzing_requests,
                                                          candidate_values_pool,
                                                          fuzzing_monitor):
    """ Prints to file statistics for request renderings.

    @param fuzzing_requests: The collection of requests to be fuzzed
    @type  fuzzing_requests: FuzzingRequestCollection
    @param candidate_values_pool: The global pool of candidate values
    @type  candidate_values_pool: CandidateValuesPool
    @param fuzzing_monitor: The global monitor of the fuzzing run
    @type  fuzzing_monitor: FuzzingMonitor

    @return: None
    @rtype : None

    """
    with open(REQUEST_RENDERING_LOGS, "a+", encoding='utf-8') as log_file:
        print(f"\n{formatting.timestamp()}: \tNever Rendered requests:", file=log_file)

        for ind, request in enumerate(fuzzing_requests):
            if fuzzing_monitor.is_fully_rendered_request(request):
                continue

            if len(request.definition) == 0:
                return

            print(f"\tRequest: {ind}", file=log_file)
            format_rendering_stats_definition(request, candidate_values_pool, log_file)

        print("-------------------------\n", file=log_file)
        log_file.flush()


def print_request_coverage(request=None, rendered_sequence=None, log_rendered_hash=True):
    """ Prints the coverage information for a request to the spec
    coverage file.  Pre-requisite: the file contains a json dictionary with
    zero or more elements.  The json object will be written into the
    top-level object.

    @param rendered_sequence: The rendered sequence
    @type  rendered_sequence: RenderedSequence

    @return: None
    @rtype : None

    """
    SpecCoverageLog.Instance().log_request_coverage_incremental(request, rendered_sequence, log_rendered_hash)


def generate_summary_speccov():
    """ Takes the existing spec coverage file and generates a new file that aggregates the data by request type

    @return: None
    @rtype : None
    """
    SpecCoverageLog.Instance().generate_summary_speccov()
