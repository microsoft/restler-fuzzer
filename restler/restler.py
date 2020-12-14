# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Main application entrypoint.

To see all supported arguments type: python restler.py -h

"""
from __future__ import print_function
from subprocess import call

import os
import sys
import signal
import time
import json
import importlib
import importlib.util
import shutil
import argparse
import checkers
import restler_settings
import atexit
from threading import Thread

import utils.logger as logger
import engine.bug_bucketing as bug_bucketing
import engine.dependencies as dependencies
import engine.core.preprocessing as preprocessing
import engine.core.postprocessing as postprocessing
import engine.core.driver as driver
import engine.core.fuzzer as fuzzer
import engine.core.fuzzing_monitor as fuzzing_monitor
import engine.core.requests as requests
from engine.errors import InvalidDictionaryException
from engine.errors import NoTokenSpecifiedException
from engine.primitives import InvalidDictPrimitiveException
from engine.primitives import UnsupportedPrimitiveException

MANAGER_HANDLE = None

def import_grammar(path):
    """ Imports grammar from path. Must work with relative and full paths.

    @param path: The path to import grammar from.
    @type  path: Str

    @return: The RequestCollection constructed from grammar in @param path.
    @rtype: RequestCollection class object.

    """
    grammar_name = os.path.basename(path).replace(".py", "")
    grammar_file = f'restler_grammar_{grammar_name}_{os.getpid()}.py'

    # import req_collection from given grammar
    sys.path.append(os.path.dirname(path))
    grammar = importlib.import_module(grammar_name)
    req_collection = getattr(grammar, "req_collection")
    # copy grammar inside experiment's folder (for debugging purposes mainly)
    try:
        target_path = os.path.join(logger.EXPERIMENT_DIR, grammar_file)
        shutil.copyfile(path, target_path)
    except shutil.Error:
        pass

    return req_collection

def get_checker_list(req_collection, fuzzing_requests, enable_list, disable_list, set_enable_first, custom_checkers, enable_default_checkers=True):
    """ Initializes all of the checkers, sets the appropriate checkers
    as enabled/disabled, and returns a list of checker objects

    Note: Order may matter for checkers, in the sense that some checkers (like
    the namespacechecker) reset the state before fuzzing, while others (like the
    use-after-free checker) start operating immediately after the main driver.
    Thus, to be safe, we do not want to reorder the checkers.

    The checkers (at least in Python 2.7) are added to the list in the order
    that they are imported, which is defined in checkers/__init__.py.

    InvalidDynamicObjectChecker was put to the back of the checker order,
    so it doesn't interfere with the others. It also re-renders all of the
    sequences that it needs itself, so it shouldn't be affected by the other
    checkers either.

    As long as the checkers are not re-ordered there shouldn't be any issue with
    skipping some. They don't rely on each other, but it's possible that some
    checkers could affect the fuzzing state in such a way that the next checker
    could behave incorrectly. For instance, LeakageRule needs to use the
    last_rendering_cache from the Fuzz, so we don't want that to be affected by
    another checker (this is why it is run first).

    @param req_collection: The global request collection
    @type  req_collection: RequestCollection
    @param fuzzing_requests: The collection of requests to fuzz
    @type  fuzzing_requests: FuzzingRequestCollection
    @param enable_list: The user-specified list of checkers to enable
    @type  enable_list: List[str]
    @param disable_list: The user-specified list of checkers to disable
    @type  disable_list: List[str]
    @param set_enable_first: This sets the ordering priority for the cases where
                            the user specifies the same checker in both lists.
                            If this is True, set the enabled values first and then
                            set the disabled values (or vice-versa if False).
    @type  set_enable_first: Bool
    @param custom_checkers: List of paths to custom checker python files
    @type  custom_checkers: List[str]
    @param enable_default_checkers: If set to False, each checker will be disabled by default,
                                    otherwise, checkers will be enabled/disabled based on their
                                    default settings.
    @type  enable_default_checkers: Bool

    @return: List of Checker objects to apply
    @rtype : List[Checker]

    """
    # Add any custom checkers
    for custom_checker_file_path in custom_checkers:
        try:
            spec = importlib.util.spec_from_file_location('custom_checkers', custom_checker_file_path)
            checker = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(checker)
            logger.write_to_main(f"Loaded custom checker from {custom_checker_file_path}", print_to_console=True)
        except Exception as err:
            logger.write_to_main(f"Failed to load custom checker {custom_checker_file_path}: {err!s}", print_to_console=True)
            sys.exit(-1)

    # Initialize the checker subclasses from CheckerBase
    available_checkers = [checker(req_collection, fuzzing_requests)\
        for checker in checkers.CheckerBase.__subclasses__()]

    # Set the first and second lists based on the set_enable_first Bool
    if set_enable_first:
        first_list = enable_list
        second_list = disable_list
        first_enable = True
        second_enable = False
    else:
        first_list = disable_list
        second_list = enable_list
        first_enable = False
        second_enable = True

    # Convert lists to lowercase for case-insensitive comparisons
    first_list = [x.lower() for x in first_list]
    second_list = [x.lower() for x in second_list]

    if '*' in second_list:
        second_list = []
        for checker in available_checkers:
            second_list.append(checker.friendly_name)
    # If the second list (priority list) is set to all,
    # do not use the first list
    elif '*' in first_list:
        first_list = []
        for checker in available_checkers:
            first_list.append(checker.friendly_name)

    # Iterate through each checker and search for its friendly name
    # in each list of enabled/disabled
    for checker in available_checkers:
        if not enable_default_checkers:
            checker.enabled = False
        if checker.friendly_name in first_list:
            checker.enabled = first_enable
        if checker.friendly_name in second_list:
            checker.enabled = second_enable

    return available_checkers

def signal_handler(sig, frame):
        print("You pressed Ctrl+C!")
        # Stop the Sync Manager process to avoid a zombie process
        global MANAGER_HANDLE
        if MANAGER_HANDLE != None:
            MANAGER_HANDLE.shutdown()
        sys.exit(0)

if __name__ == '__main__':

    # the following intercepts Ctrl+C (tested on Windows only! but should work on Linux)
    # the next line works in powershell (but not in bash on Windows!)
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument('--max_sequence_length',
                        help='Max number of requests in a sequence'
                            f' (default: {restler_settings.MAX_SEQUENCE_LENGTH_DEFAULT})',
                        type=int, default=restler_settings.MAX_SEQUENCE_LENGTH_DEFAULT, required=False)
    parser.add_argument('--fuzzing_jobs',
                        help='Number of fuzzing jobs to run in parallel'
                             ' (default: 1)',
                        type=int, default=1, required=False)
    parser.add_argument('--target_ip', help='Target IP',
                        type=str, default=None, required=False)
    parser.add_argument('--target_port', help='Target Port',
                        type=int, default=None, required=False)
    parser.add_argument('--time_budget', help='Stops fuzzing after given time'
                        ' in hours (default: one month)',
                        type=float, default=restler_settings.TIME_BUDGET_DEFAULT, required=False)
    parser.add_argument('--max_request_execution_time',
                        help='The time interval in seconds to wait for a request to complete,'
                            'after which a timeout should be reported as a bug. '
                            f' (default: {restler_settings.MAX_REQUEST_EXECUTION_TIME_DEFAULT} seconds,'
                            f' maximum: {restler_settings.MAX_REQUEST_EXECUTION_TIME_MAX}) seconds.',
                        type=float, default=restler_settings.MAX_REQUEST_EXECUTION_TIME_DEFAULT, required=False)
    parser.add_argument('--fuzzing_mode',
                        help='Fuzzing mode.'
                             ' One of bfs/bfs-fast/bfs-cheap/bfs-minimal/random-walk/'
                             f'directed-smoke-test (default: {restler_settings.FUZZING_MODE_DEFAULT})',
                        type=str, default=restler_settings.FUZZING_MODE_DEFAULT, required=False)
    parser.add_argument('--ignore_feedback',
                        help='Ignore server-side feedback (default: False)',
                        type=bool, default=False, required=False)
    parser.add_argument('--ignore_dependencies',
                        help='Ignore request dependencies (default: False)',
                        type=bool, default=False, required=False)
    parser.add_argument('--garbage_collection_interval',
                        help='Perform async. garbage collection of dynamic '
                        'objects (Default: off).',
                        type=int, required=False)
    parser.add_argument('--dyn_objects_cache_size',
                        help='Max number of objects of one type before deletion by the garbage collector '
                        f'(default: {restler_settings.DYN_OBJECTS_CACHE_SIZE_DEFAULT}).',
                        type=int, default=restler_settings.DYN_OBJECTS_CACHE_SIZE_DEFAULT, required=False)
    parser.add_argument('--restler_grammar',
                        help='RESTler grammar definition. Overrides parsing of'
                            ' swagger specification',
                        type=str, default='', required=False)
    parser.add_argument('--custom_mutations',
                        help='Custom pool of primitive type values. Note that'
                            ' custom mutations will be erased in case'
                            ' checkpoint files exist',
                        type=str, default='', required=False)
    parser.add_argument('--settings',
                        help='Custom user settings file path',
                        type=str, default='', required=False)
    parser.add_argument('--path_regex',
                        help='Limit restler grammars only to endpoints whose'
                        'paths contains a given substing',
                        type=str, default=None, required=False)
    parser.add_argument('--token_refresh_interval',
                        help='Interval to periodically refreshes token (in seconds)'
                            ' (default: None)',
                       type=int, default=None, required=False)
    parser.add_argument('--token_refresh_cmd',
                        help='The cmd to execute in order to refresh the authentication token'
                            ' (default: None)',
                       type=str, default=None, required=False)
    parser.add_argument('--producer_timing_delay',
                        help='The time interval to wait after a resource-generating '
                             'producer is executed (in seconds)'
                            ' (default: 0 -- no delay)',
                       type=int, default=0, required=False)
    parser.add_argument('--no_tokens_in_logs',
                        help='Do not print auth token data in logs (default: False)',
                        type=bool, default=False, required=False)
    parser.add_argument('--host',
                        help='Set to override Host in the grammar (default: do not override)',
                        type=str, default=None, required=False)
    parser.add_argument('--no_ssl',
                        help='Set this flag if you do not want to use SSL validation for the socket',
                        action='store_true')
    parser.add_argument('--include_user_agent',
                        help='Set this flag if you would like to add User-Agent to the request headers',
                        action='store_true')
    parser.add_argument('--enable_checkers',
                        help='Follow with a list of checkers to force those checkers to be enabled',
                        type=str, nargs='+', required=False)
    parser.add_argument('--disable_checkers',
                        help='Follow with a list of checkers to force those checkers to be disabled',
                        type=str, nargs='+', required=False)
    parser.add_argument('--replay_log',
                        help='A log containing a sequence of requests to send to the server',
                        type=str, default=None, required=False)
    parser.add_argument('--use_test_socket',
                        help='Set to use the test socket',
                        action='store_true')
    parser.add_argument('--test_server',
                        help='Set the test server to run',
                        type=str, default=restler_settings.DEFAULT_TEST_SERVER_ID, required=False)
    parser.add_argument('--set_version',
                        help="Sets restler's version",
                        type=str, default=None, required=False)
    args = parser.parse_args()

    settings_file = None

    if bool(args.settings):
        try:
            settings_file = json.load(open(args.settings))
        except Exception as error:
            print(f"Error: Failed to load settings file: {error!s}")
            sys.exit(-1)

    # convert the command-line arguments to a dict
    user_args = vars(args)
    # combine settings from settings file to the command-line arguments
    if settings_file:
        user_args.update(settings_file)
        user_args['settings_file_exists'] = True

    if args.restler_grammar:
        # Set grammar schema to the same path as the restler grammar, but as json
        args.grammar_schema = '.json'.join(args.restler_grammar.rsplit('.py', 1))

    try:
        # Set the restler settings singleton
        settings = restler_settings.RestlerSettings(user_args)
    except restler_settings.InvalidValueError as error:
        print(f"\nArgument Error::\n\t{error!s}")
        sys.exit(-1)
    except Exception as error:
        print(f"\nFailed to parse user settings file: {error!s}")
        sys.exit(-1)

    try:
        settings.validate_options()
    except restler_settings.OptionValidationError as error:
        print(f"\nArgument Error::\n\t{error!s}")
        sys.exit(-1)

    # Options Validation
    custom_mutations = {}
    if not args.replay_log:
        if not args.restler_grammar:
            print("\nArgument Error::\n\tNo restler grammar was provided.\n")
            sys.exit(-1)
        if settings.fuzzing_mode not in ['bfs', 'bfs-cheap'] and args.fuzzing_jobs > 1:
            print("\nArgument Error::\n\tOnly bfs supports multiple fuzzing jobs\n")
            sys.exit(-1)

        if args.custom_mutations:
            try:
                custom_mutations = json.load(open(args.custom_mutations))
            except Exception as error:
                print(f"Cannot import custom mutations: {error!s}")
                sys.exit(-1)

    # Create the directory where all the results will be saved
    try:
        logger.create_experiment_dir()
    except Exception as err:
        print(f"Failed to create logs directory: {err!s}")
        sys.exit(-1)

    if settings.no_tokens_in_logs:
        logger.no_tokens_in_logs()

    if args.replay_log:
        try:
            logger.create_network_log(logger.LOG_TYPE_REPLAY)
            driver.replay_sequence_from_log(args.replay_log, settings.token_refresh_cmd)
            print("Done playing sequence from log")
            sys.exit(0)
        except NoTokenSpecifiedException:
            logger.write_to_main(
                "Failed to play sequence from log:\n"
                "A valid authorization token was expected.\n"
                "Retry with a token refresh script in the settings file or "
                "update the request in the replay log with a valid authorization token.",
                print_to_console=True
            )
            sys.exit(-1)
        except Exception as error:
            print(f"Failed to play sequence from log:\n{error!s}")
            sys.exit(-1)

    # Import grammar from a restler_grammar file
    if args.restler_grammar:
        try:
            req_collection = import_grammar(args.restler_grammar)
            req_collection.set_grammar_name(args.restler_grammar)
        except Exception as error:
            print(f"Cannot import grammar: {error!s}")
            sys.exit(-1)

    # Create the request collection singleton
    requests.GlobalRequestCollection(req_collection)

    # Override default candidate values with custom mutations
    custom_mutations_paths = settings.get_endpoint_custom_mutations_paths()
    per_endpoint_custom_mutations = {}
    if custom_mutations_paths:
        for endpoint in custom_mutations_paths:
            try:
                if os.path.isabs(custom_mutations_paths[endpoint]):
                    path = custom_mutations_paths[endpoint]
                else:
                    # If custom dictionary path is not an absolute path, make it relative to the grammar
                    path = os.path.join(os.path.dirname(args.restler_grammar), custom_mutations_paths[endpoint])
                with open(path, 'r') as mutations:
                    per_endpoint_custom_mutations[endpoint] = json.load(mutations)
            except Exception as error:
                print(f"Cannot import custom mutations: {error!s}")
                sys.exit(-1)

    try:
        req_collection.set_custom_mutations(custom_mutations, per_endpoint_custom_mutations)
    except UnsupportedPrimitiveException as primitive:
        logger.write_to_main("Error in mutations dictionary.\n"
                            f"Unsupported primitive type defined: {primitive!s}",
                            print_to_console=True)
        sys.exit(-1)
    except InvalidDictPrimitiveException as err:
        logger.write_to_main("Error in mutations dictionary.\n"
                             "Dict type primitive was specified as another type.\n"
                            f"{err!s}",
                            print_to_console=True)
        sys.exit(-1)

    if settings.token_refresh_cmd:
        req_collection.candidate_values_pool.set_candidate_values(
            {
                'restler_refreshable_authentication_token':
                    {
                        'token_refresh_cmd': settings.token_refresh_cmd,
                        'token_refresh_interval': settings.token_refresh_interval
                    }
            }
        )
    else:
        req_collection.remove_authentication_tokens()

    # Initialize the fuzzing monitor
    monitor = fuzzing_monitor.FuzzingMonitor()

    # pass some user argument internally to request_set
    monitor.set_time_budget(settings.time_budget)
    monitor.renderings_monitor.set_memoize_invalid_past_renderings_on()

    if settings.host:
        try:
            req_collection.update_hosts()
        except requests.InvalidGrammarException:
            sys.exit(-1)
    else:
        host = req_collection.get_host_from_grammar()
        if host is not None:
            if ':' in host:
                # If hostname includes port, split it out
                host_split = host.split(':')
                host = host_split[0]
                if settings.connection_settings.target_port is None:
                    settings.set_port(host_split[1])
            settings.set_hostname(host)
        else:
            logger.write_to_main(
                "Host not found in grammar. "
                "Add the host to your spec or launch RESTler with --host parameter.",
                 print_to_console=True
            )
            sys.exit(-1)

    # Filter and get the requests to be used for fuzzing
    fuzzing_requests = preprocessing.create_fuzzing_req_collection(args.path_regex)

    # Initialize bug buckets
    bug_bucketing.BugBuckets()

    # If both lists were set, parse the command-line to find the order
    if args.enable_checkers and args.disable_checkers:
        set_enable_first = sys.argv.index('--enable_checkers') < sys.argv.index('--disable_checkers')
    else:
        set_enable_first = args.enable_checkers is not None

    checkers = get_checker_list(req_collection, fuzzing_requests, args.enable_checkers or [], args.disable_checkers or [],\
        set_enable_first, settings.custom_checkers, enable_default_checkers=args.fuzzing_mode != 'directed-smoke-test')

    # Initialize request count for each checker
    for checker in checkers:
        if checker.enabled:
            monitor.status_codes_monitor._requests_count[checker.__class__.__name__] = 0

    try:
        destructors = preprocessing.apply_create_once_resources(fuzzing_requests)
    except preprocessing.CreateOnceFailure as failobj:
        logger.write_to_main(
            failobj.msg,
            print_to_console=True
        )
        postprocessing.delete_create_once_resources(failobj.destructors, fuzzing_requests)
        if settings.in_smoke_test_mode():
            logger.print_spec_coverage(fuzzing_requests)
        sys.exit(-1)
    except InvalidDictionaryException:
        print(f"Failed preprocessing:\n\t"
               "An error was identified in the dictionary.")
        sys.exit(-1)
    except Exception as error:
        print(f"Failed preprocessing:\n\t{error!s}")
        sys.exit(-1)

    grammar_path = settings.grammar_schema
    if os.path.exists(grammar_path):
        try:
            with open(grammar_path, 'r') as grammar:
                schema_json = json.load(grammar)
        except Exception as err:
            logger.write_to_main(f"Failed to process grammar file: {grammar_path}; {err!s}", print_to_console=True)
            sys.exit(-1)

        if not preprocessing.parse_grammar_schema(schema_json):
            sys.exit(-1)
    else:
        logger.write_to_main(f"Grammar schema file '{grammar_path}' does not exist.", print_to_console=True)

    # Start fuzzing
    fuzz_thread = fuzzer.FuzzingThread(fuzzing_requests, checkers, args.fuzzing_jobs)
    fuzz_thread.setName('Fuzzer')
    fuzz_thread.setDaemon(True)
    fuzz_thread.start()

    gc_thread = None
    # Start the GC thread if specified
    if args.garbage_collection_interval:
        print(f"Initializing: Garbage collection every {settings.garbage_collection_interval} seconds.")
        gc_thread = dependencies.GarbageCollectorThread(req_collection, monitor, settings.garbage_collection_interval)
        gc_thread.setName('Garbage Collector')
        gc_thread.setDaemon(True)
        gc_thread.start()

    THREAD_JOIN_WAIT_TIME_SECONDS = 1
    # Wait for the fuzzing job to end before continuing.
    # Looping in case the gc_thread terminates prematurely.
    # We don't want to keep fuzzing if GC stopped working
    num_total_sequences = 0
    while fuzz_thread.is_alive():
        if gc_thread and not gc_thread.is_alive():
            logger.write_to_main(
                "Garbage collector thread has terminated prematurely", print_to_console=True
            )
            # Terminate the fuzzing thread
            monitor.terminate_fuzzing()
        num_total_sequences = fuzz_thread.join(THREAD_JOIN_WAIT_TIME_SECONDS)

    try:
        # Attempt to delete the create_once resources.
        # Note: This is done in addition to attempting to use the garbage collector.
        #   The garbage collector can handle cleaning up resources with destructors
        #   that were not excluded from fuzzing. This post-processing event can clean
        #   up those resources that were excluded. This happens when a create_once
        #   resource was the parent resource in a request.
        postprocessing.delete_create_once_resources(destructors, fuzzing_requests)
    except Exception as error:
        print("Exception occurred in delete create_once_resources: {}".
            format(str(error)))

    if settings.in_smoke_test_mode():
        logger.print_spec_coverage(fuzzing_requests)

    # If garbage collection is on, deallocate everything possible.
    if gc_thread:
        print("Terminating garbage collection. Waiting for max {} seconds.".\
              format(settings.garbage_collector_cleanup_time))
        gc_thread.finish(settings.garbage_collector_cleanup_time)
        # Wait for GC to complete
        # Loop in order to enable the signal handler to run,
        # otherwise CTRL-C does not work.
        while gc_thread.is_alive():
            gc_thread.join(THREAD_JOIN_WAIT_TIME_SECONDS)

    # Print the end of the run generation stats
    logger.print_generation_stats(req_collection, monitor, None, final=True)

    if fuzz_thread.exception is not None:
        print(fuzz_thread.exception)
        sys.exit(-1)

    print("Done.")
