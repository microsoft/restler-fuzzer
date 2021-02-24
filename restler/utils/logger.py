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
from collections import OrderedDict
from shutil import copyfile
from collections import namedtuple

import engine.primitives as primitives
import engine.dependencies as dependencies

import utils.formatting as formatting

PREPROCESSING_GENERATION = -1
POSTPROCESSING_GENERATION = -2

SETTINGS_NO_TOKENS_IN_LOGS = False

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
        if os.path.getsize(self._current_log_path) > NetworkLog._MaxLogSize:
            # Create a new log if the current log has grown beyond the max size
            self._current_log_num += 1
            self._current_log_path = build_logfile_path(
                NETWORK_LOGS, self._log_name, self._thread_id, self._current_log_num)

        with open(self._current_log_path, 'a+', encoding='utf-8') as log_file:
            print(data, file=log_file)
            log_file.flush()
            os.fsync(log_file.fileno())

def no_tokens_in_logs():
    """ Do not print token data in logs
    @return: None
    @rtype: None
    """
    global SETTINGS_NO_TOKENS_IN_LOGS
    SETTINGS_NO_TOKENS_IN_LOGS = True
    return

def create_experiment_dir():
    """ creates the unique EXPERIMENT_DIR directory where results are saved
    @return: None
    @rtype: None
    """
    global EXPERIMENT_DIR
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
    with open(filename, "a+") as log_file:
        print(msg, file=log_file)

main_lock = threading.Semaphore(1)
def write_to_main(data: str, print_to_console: bool=False):
    """ Writes to the main log

    @param data: The data to write
    @param print_to_console: If true, print to console as well as log

    @return: None

    """
    try:
        main_lock.acquire()
        with open(MAIN_LOGS, "a+") as f:
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
        for request_block in definition:
            primitive = request_block[0]
            default_val = request_block[1]
            quoted = request_block[2]
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
            elif primitive == "restler_custom_payload_header":
                current_fuzzable_tag = default_val
                values = candidate_values_pool.get_candidate_values(primitive, request_id=request.request_id, tag=current_fuzzable_tag, quoted=quoted)
                if not isinstance(values, list):
                    values = [values]
                if len(values) == 1:
                    default_val = values[0]
            # Handle custom payload
            elif primitive == "restler_custom_payload":
                current_fuzzable_tag = default_val
                values = candidate_values_pool.get_candidate_values(primitive, request_id=request.request_id, tag=current_fuzzable_tag, quoted=quoted)
                if not isinstance(values, list):
                    values = [values]
                if len(values) == 1:
                    default_val = values[0]
            # Handle custom payload with uuid4 suffix
            elif primitive == "restler_custom_payload_uuid4_suffix":
                current_fuzzable_tag = default_val
                values = candidate_values_pool.get_candidate_values(primitive, request_id=request.request_id, tag=current_fuzzable_tag, quoted=quoted)
                default_val = values[0]
            # Handle all the rest
            else:
                values = candidate_values_pool.get_fuzzable_values(primitive, default_val, request.request_id, quoted=quoted)

            if len(values) > 1:
                network_log.write(f"\t\t+ {primitive}: {values}")
            else:
                print_val = values[0] if values else default_val
                network_log.write(f"\t\t- {primitive}: {print_val!r}")
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
    def log_new_bug():
        # Create the new bug log
        filename = f"{bucket_class}_{len(bug_buckets[bucket_class].keys())}.txt"
        filepath = os.path.join(BUG_BUCKETS_DIR, filename)

        with open(filepath, "w+") as bug_file:
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

    def add_hash(replay_filename):
        """ Helper that adds bug hash to the bug buckets json file """
        global Bug_Hashes
        Bug_Hashes[bug_hash] = {"file_path": replay_filename}
        with open(os.path.join(BUG_BUCKETS_DIR, "bug_buckets.json"), "w+") as hash_json:
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
    with open(filename, "w+") as log_file:
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

    with open(ASYNC_LOG, "a+") as f:
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
    data += f"{timestamp}: Total dependencies: {val}"

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
        f"{timestamp}: Bug Buckets: {BugBuckets.Instance().num_bug_buckets()}"
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

        with open(os.path.join(LOGS_DIR, "testing_summary.json"), "w+") as summary_json:
            json.dump(testing_summary, summary_json, indent=4)

def format_rendering_stats_definition(request, candidate_values_pool, log_file=None):
    for request_block in request.definition:
        primitive = request_block[0]
        default_val = request_block[1]
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
        elif primitive == "restler_custom_payload":
            current_fuzzable_tag = default_val
            values = candidate_values_pool.get_candidate_values(primitive, request_id=request.request_id, tag=current_fuzzable_tag)
            if not isinstance(values, list):
                values = [values]
            if len(values) == 1:
                default_val = values[0]
        # Handle custom payload header
        elif primitive == "restler_custom_payload_header":
            current_fuzzable_tag = default_val
            values = candidate_values_pool.get_candidate_values(primitive, request_id=request.request_id, tag=current_fuzzable_tag)
            if not isinstance(values, list):
                values = [values]
            if len(values) == 1:
                default_val = values[0]

        elif primitive == "restler_custom_payload_uuid4_suffix":
            current_fuzzable_tag = default_val
            values = candidate_values_pool.get_candidate_values(primitive, request_id=request.request_id, tag=current_fuzzable_tag)
            default_val = values[0]
        # Handle all the rest
        else:
            values = candidate_values_pool.get_candidate_values(primitive, request_id=request.request_id)

        if len(values) > 1:
            data = f"\t\t+ {primitive}: {values}"
        else:
            data = f"\t\t- {primitive}: {default_val[:100]!r}"

        if log_file:
            print(data, file=log_file)
        else:
            write_to_main(data)

    if log_file:
        print("", file=log_file)
    else:
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

    with open(REQUEST_RENDERING_LOGS, "a+") as log_file:
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
    with open(REQUEST_RENDERING_LOGS, "a+") as log_file:
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

def print_spec_coverage(fuzzing_requests):
    """ Prints the speccov run summary in json format

    @param fuzzing_requests: The fuzzing request collection
    @type  fuzzing_requests: FuzzingRequests

    @return: None
    @rtype : None

    """
    from engine.core.requests import FailureInformation
    # Sort the requests by request_order
    spec_list = fuzzing_requests.preprocessing_requests + \
                sorted(fuzzing_requests.requests, key=lambda x : x.stats.request_order) + \
                fuzzing_requests.postprocessing_requests

    spec_file = OrderedDict()
    for req in spec_list:
        spec_file[req.method_endpoint_hex_definition] = {}
        req_spec = spec_file[req.method_endpoint_hex_definition]
        req_spec['verb'] = req.method
        req_spec['endpoint'] = req.endpoint_no_dynamic_objects
        req_spec['verb_endpoint'] = f"{req.method} {req.endpoint_no_dynamic_objects}"
        req_spec['valid'] = req.stats.valid
        if req.stats.matching_prefix:
            req_spec['matching_prefix'] = req.stats.matching_prefix
        else:
            req_spec['matching_prefix'] = 'None'
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
        req_spec['status_code'] = req.stats.status_code
        req_spec['status_text'] = req.stats.status_text
        req_spec['error_message'] = req.stats.error_msg
        req_spec['request_order'] = req.stats.request_order

    with open(os.path.join(LOGS_DIR, 'speccov.json'), 'w') as file:
        json.dump(spec_file, file, indent=4)
