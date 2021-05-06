# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Implements core sequence generation logic. """
from __future__ import print_function
import sys, os
import copy
import time
import random
import inspect
import itertools
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool
from collections import deque
import re

from restler_settings import Settings
import utils.logger as logger
import utils.saver as saver
import utils.formatting as formatting
import engine.dependencies as dependencies
import engine.core.sequences as sequences
import engine.core.requests as requests
import engine.core.fuzzing_monitor as fuzzing_monitor
from engine.core.fuzzing_requests import FuzzingRequestCollection
from engine.core.requests import GrammarRequestCollection
from engine.core.requests import FailureInformation
from engine.core.request_utilities import execute_token_refresh_cmd
from engine.core.request_utilities import get_hostname_from_line
from engine.core.fuzzing_monitor import Monitor
from engine.errors import TimeOutException
from engine.errors import ExhaustSeqCollectionException
from engine.errors import InvalidDictionaryException
from engine.transport_layer import messaging
from utils.logger import raw_network_logging as RAW_LOGGING

def validate_dependencies(consumer_req, producer_seq):
    """ Validates that the dependencies required by a consumer are a subset of
    those produced by a set of requests. This routine is useful to decide whether
    it is reasonable to append a request at the end of a sequence or not.

    @param consumer_req: A request.
    @type  consumer_req: Request class object.
    @param producer_seq: A sequence.
    @type  producer_seq: Sequence class object.

    @return: True if producer sequence satisfies consumer request's dependencies.
    @rtype : Bool

    """
    producer_requests = []
    for req in producer_seq:
        producer_requests.extend(req.produces)
    return consumer_req.consumes <= set(producer_requests)


def extend(seq_collection, fuzzing_requests, lock):
    """ Extends each sequence currently present in collection by any request
    from request collection whose dependencies can be resolved if appended at
    the end of the target sequence.

    @param seq_collection: List of sequences in sequence collection.
    @type  seq_collection: List
    @param fuzzing_requests: The collection of requests to fuzz.
    @type  fuzzing_requests: FuzzingRequestCollection.
    @param lock: Lock object used for sync of more than one fuzzing jobs.
    @type  lock: thread.Lock object

    @return: The list of newly enxtended sequences.
    @rtype : List

    """
    prev_len = len(seq_collection)
    extended_requests = []

    # The functions that access the monitor of renderings (e.g.,
    # "is_fully_rendered_request" and "num_fully_rendered_requests") answer
    # based on the latest _completed_ generation and the internal
    # counter that tracks the latest completed fuzzing generation is increased
    # after the end of @function render. However, inside the driver main-loop we
    # first run @function extend (since initially we start by an empty
    # sequence) and then run @function render, and thus, we need to temporarily
    # increase the generation counter in order to get a proper behaviour
    # when invoking "is_fully_rendered_request" in here after the first iteration
    # of the main-loop.
    Monitor().current_fuzzing_generation += 1

    for req in fuzzing_requests:
        for i in range(prev_len):
            seq = seq_collection[i]

            # Extend sequence collection by adding requests that have
            # valid dependencies and skip the rest
            if not validate_dependencies(req, seq)\
                    and not Settings().ignore_dependencies:
                continue

            extended_requests.append(req)
            req_copy = copy.copy(req)
            req_copy._current_combination_id = 0
            if seq.is_empty_sequence():
                new_seq = sequences.Sequence(req_copy)
            else:
                new_seq = seq + sequences.Sequence(req_copy)

            seq_collection.append(new_seq)

            # In 'quick' modes, append each request to exactly one sequence
            if Settings().fuzzing_mode in \
                    ['bfs-fast', 'bfs-minimal', 'directed-smoke-test']:
                break

    # See comment above...
    Monitor().current_fuzzing_generation -= 1

    # In case of random walk, truncate sequence collection to
    # one randomly selected sequence
    if Settings().fuzzing_mode == 'random-walk':
        if len(seq_collection) > 0:
            rand_int = random.randint(prev_len, len(seq_collection) - 1)
            return seq_collection[rand_int: rand_int + 1], extended_requests[rand_int: rand_int + 1]
        else:
            return [], []

    # Drop previous generation and keep current extended generation
    return seq_collection[prev_len:], extended_requests


def apply_checkers(checkers, renderings, global_lock):
    """ Calls each enabled checker from a list of Checker objects

    @param checkers: A list of checkers to apply
    @type  checkers: List[Checker]
    @param renderings: Object containing the rendered sequence information
    @type  renderings: RenderedSequence
    @param global_lock: Lock object used for sync of more than one fuzzing jobs.
    @type  global_lock: thread.Lock

    @return: None
    @rtype : None

    """
    for checker in checkers:
        try:
            if checker.enabled:
                RAW_LOGGING(f"Checker: {checker.__class__.__name__} kicks in\n")
                checker.apply(renderings, global_lock)
                RAW_LOGGING(f"Checker: {checker.__class__.__name__} kicks out\n")
        except Exception as error:
            print(f"Exception {error!s} applying checker {checker}")
            raise


def render_one(seq_collection, ith, checkers, generation, global_lock):
    """ Render ith sequence from sequence collection.

    @param seq_collection: List of sequences in sequence collection.
    @type  seq_collection: List
    @param ith: The position of the target sequence (to be rendered) in the
                    sequence collection.
    @type  ith: Int
    @param checkers: The list of checkers to apply
    @type  checkers: list[Checker]
    @param generation: The fuzzing generation
    @type  generation: Int
    @param global_lock: Lock object used for sync of more than one fuzzing jobs.
    @type  global_lock: thread.Lock object

    @return: The list of sequences with valid renderings.
    @rtype : List

    Note: Try ith sequence's template with all posible primitive type value
    combinations and return only renderings (combinations of primitive type
    values) that lead to valid error codes. We keep track of the order of the
    current sequence in the collection using "ith" argument for logging
    purposes.

    """
    # Log memory consumption every hour.
    n_minutes = 60

    # Static variable used for keeping track of the last time memory consumption was printed
    render_one.last_memory_consumption_check = getattr(render_one, 'last_memory_consumption_check', int(time.time()))

    if int(time.time()) - render_one.last_memory_consumption_check > (n_minutes*60):
        logger.print_memory_consumption(GrammarRequestCollection(), Monitor(), Settings().fuzzing_mode, generation)
        render_one.last_memory_consumption_check = int(time.time())

    candidate_values_pool = GrammarRequestCollection().candidate_values_pool
    current_seq = seq_collection[ith]
    current_seq.seq_i = ith
    valid_renderings = []
    prev_renderings = None

    # Try to find one valid rendering.
    n_invalid_renderings = 0
    while True:
        # Render on a sequence instance will internally iterate over  possible
        # renderings of current sequence until a valid or an invalid combination
        # of values for its primitive types is found -- internal iteration may
        # skip some renderings (that are marked to be skipped according to past
        # failures) -- that's why we put everything in a while.
        renderings = current_seq.render(candidate_values_pool, global_lock)

        # Note that this loop will keep running as long as we hit invalid
        # renderings and we will end up reapplying the leakage rule a billion
        # times for very similar 404s. To control this, when in bfs-cheap, we
        # apply the checkers only on the first invalid rendering.
        if Settings().fuzzing_mode not in ['bfs-cheap', 'bfs-minimal']\
                or renderings.valid or n_invalid_renderings < 1:
            apply_checkers(checkers, renderings, global_lock)

        # If renderings.sequence is None it means there is nothing left to render.
        if renderings.sequence is None:
            break

        # If in exhaustive test mode, log the spec coverage.
        if Settings().fuzzing_mode == 'all-renderings-test':
            renderings.sequence.last_request.stats.set_all_stats(renderings)
            logger.print_request_coverage_incremental(renderings, log_rendered_hash=True)

        # Exit after a valid rendering was found
        if renderings.valid:
            break

        # This line will only be reached only if we have an invalid rendering or testing all renderings exhaustively.
        n_invalid_renderings += 1

        # Save the previous rendering in order to log statistics in cases when all renderings
        # were invalid
        prev_renderings = renderings

    # for random-walk and cheap fuzzing, one valid rendering is enough.
    # for directed smoke test mode, only a single valid rendering is needed.
    if Settings().fuzzing_mode in ['random-walk',  'bfs-cheap', 'bfs-minimal', 'directed-smoke-test']:
        if renderings.valid:
            valid_renderings.append(renderings.sequence)

        # If in test mode, log the spec coverage.
        if Settings().fuzzing_mode == 'directed-smoke-test':
            logged_renderings = renderings if renderings.sequence else prev_renderings
            logged_renderings.sequence.last_request.stats.set_all_stats(logged_renderings)
            logger.print_request_coverage_incremental(logged_renderings, log_rendered_hash=True)

    # bfs needs to be exhaustive to provide full grammar coverage
    elif Settings().fuzzing_mode in ['bfs', 'bfs-fast', 'all-renderings-test']:

        # This loop will iterate over possible remaining renderings of the
        # current sequence.
        while renderings.sequence is not None:
            if renderings.valid:
                valid_renderings.append(renderings.sequence)
            renderings = current_seq.render(candidate_values_pool, global_lock)
            apply_checkers(checkers, renderings, global_lock)

            # If in exhaustive test mode, log the spec coverage.
            if renderings.sequence:
                if Settings().fuzzing_mode == 'all-renderings-test':
                    renderings.sequence.last_request.stats.set_all_stats(renderings)
                    logger.print_request_coverage_incremental(renderings, log_rendered_hash=True)

                # Save the previous rendering in order to log statistics in cases when all renderings
                # were invalid
                prev_renderings = renderings
    else:
        print("Unsupported fuzzing_mode:", Settings().fuzzing_mode)
        assert False

    return valid_renderings

def render_parallel(seq_collection, fuzzing_pool, checkers, generation, global_lock):
    """ Does rendering work in parallel by invoking "render_one" multiple
    times using a pool of python workers. For brevity we skip arguments and
    return types, since they are similar with "render_one".

    """
    prev_len = len(seq_collection)
    result = fuzzing_pool.starmap(render_one,
                                    [(seq_collection, ith,
                                      checkers, generation, global_lock
                                     )\
                                    for ith in range(prev_len)])
    seq_collection = list(itertools.chain(*result))

    # Increase internal fuzzing generations' counter. Since the
    # constructor of RequestCollection starts this counter from zero,
    # the counter will be equal to lenght + 1 after the following line.
    Monitor().current_fuzzing_generation += 1

    return seq_collection


def render_sequential(seq_collection, fuzzing_pool, checkers, generation, global_lock):
    """ Does rendering work sequential by invoking "render_one" multiple
    times. For brevity we skip arguments and return types, since they are
    similar with "render_one".

    """
    prev_len = len(seq_collection)
    for ith in range(prev_len):
        valid_renderings = render_one(seq_collection, ith, checkers, generation, global_lock)
        # Extend collection by adding all valid renderings
        seq_collection.extend(valid_renderings)

    if len(seq_collection[prev_len:]) == 0:
        raise ExhaustSeqCollectionException("")

    # Increase internal fuzzing generations' counter. Since the
    # constructor of RequestCollection starts this counter from zero,
    # the counter will be equal to length + 1 after the following line.
    Monitor().current_fuzzing_generation += 1

    return seq_collection[prev_len:]

def report_dependency_cycle(request, req_list):
    logger.write_to_main(
        "\nError in input grammar: a request is in a circular dependency!"
        f"\nRequest: {request.method} {request.endpoint}"
        "\n\tThe circular dependency is in the following request sequence:",
        True
        )

    for req in req_list:
        logger.write_to_main(f"\n\tRequest: {req.method} {req.endpoint}", True)
        for consumer_var_name in req.consumes:
            logger.write_to_main(f"\t\tConsumes {consumer_var_name}", True)
        for producer_var_name in req.produces:
            logger.write_to_main(f"\t\tProduces {producer_var_name}", True)

# Return properly-sorted req_list if OK, [] if error
# req_list is a request sequence ending with req and satisfying all consumer-producer dependencies
# Note: this function is recursive, but clean and recursion-depth is small
# cost is linear in the size of the returned req_list (worst-case O((n^2)/2) because of edges)
def add_producers(req, req_collection, req_list, dfs_stack):
    # cycle detection
    # Note: the next line is linear in dfs_stack but dfs_stack is usually very small (<10)
    # Note: dfs_stack is used as, and could be replaced by, a set here
    if req in dfs_stack :
        report_dependency_cycle(req, dfs_stack)
        return []
    # else append req to dfs_stack
    dfs_stack.append(req)

    # Find all other requests producing objects consumed by req
    for consumer_var_name in sorted(req.consumes):
        # Find the producer of this object
        producer_found = False
        for producer_req in req_collection:
            if consumer_var_name in producer_req.produces:
                # Producer is found
                if producer_found == True :
                    logger.write_to_main(
                        f"\nError in input grammar: {consumer_var_name} has more than one producer!\n",
                        True)
                    return []
                producer_found = True
                # If this producer is not already in req_list, add its own producers recursively...
                # Note: the next line is linear in req_list but req_list is usually very small (<10)
                if producer_req not in req_list :
                    req_list = add_producers(producer_req, req_collection, req_list, dfs_stack)
                    # if an error occurred in the sub-computation below, abort and pop-up
                    if req_list == [] :
                        return []

        if producer_found == False :
            logger.write_to_main(
                f"\nError in input grammar: {consumer_var_name} has no producer!\n",
                True)
            return []

    # Since all producers of req (if any) have been processed, add req at the end of req_list
    req_list.append(req)
    # continue the recursion by popping up
    dfs_stack.pop()
    return req_list

# Return a request sequence ending with request and satisfying all consumer-producer dependencies
# or [] if an error was encountered
def compute_request_goal_seq(request, req_collection):
    req_list = add_producers(request, req_collection, [], [])
    if req_list == [] :
        logger.write_to_main(f"\nSkipping request {request.method} {request.endpoint}\n", True)
    return req_list

def generate_sequences(fuzzing_requests, checkers, fuzzing_jobs=1):
    """ Implements core restler algorithm.

    @param fuzzing_requests: The collection of requests that will be fuzzed
    @type  fuzzing_requests: FuzzingRequestCollection
    @param checkers: The list of checkers to apply
    @type  checkers: list[Checker]
    @param fuzzing_jobs: Optional number of fuzzing jobs for parallel fuzzing.
                            Default value passed is one (sequential fuzzing).
    @type  fuzzing_jobs: Int

    @return: None
    @rtype : None

    """
    if not fuzzing_requests.size:
        return

    logger.create_network_log(logger.LOG_TYPE_TESTING)

    fuzzing_mode = Settings().fuzzing_mode
    max_len = Settings().max_sequence_length

    if fuzzing_jobs > 1:
        render = render_parallel
        global_lock = multiprocessing.Lock()
        fuzzing_pool = ThreadPool(fuzzing_jobs)
    else:
        global_lock = None
        fuzzing_pool = None
        render = render_sequential

    should_stop = False
    timeout_reached = False
    seq_collection_exhausted = False
    num_total_sequences = 0
    while not should_stop:

        seq_collection = [sequences.Sequence()]
        # Only for bfs: If any checkpoint file is available, load state of
        # latest generation. Note that it only makes sense to use checkpoints
        # for the bfs exploration method, since it is the only systemic and
        # exhaustive method.
        min_len = 0
        if fuzzing_mode == 'bfs':
            req_collection = GrammarRequestCollection()
            monitor = Monitor()
            req_collection, seq_collection, fuzzing_requests, monitor, min_len =\
                saver.load(req_collection, seq_collection, fuzzing_requests, monitor)
            requests.GlobalRequestCollection.Instance()._req_collection = req_collection
            fuzzing_monitor.FuzzingMonitor.__instance = monitor
        # Repeat external loop only for random walk
        if fuzzing_mode != 'random-walk':
            should_stop = True

        # Initialize fuzzing schedule
        fuzzing_schedule = {}
        logger.write_to_main(f"Setting fuzzing schemes: {fuzzing_mode}")
        for length in range(min_len, max_len):
            fuzzing_schedule[length] = fuzzing_mode
            # print(" - {}: {}".format(length + 1, fuzzing_schedule[length]))

        # print general request-related stats
        logger.print_req_collection_stats(
            fuzzing_requests, GrammarRequestCollection().candidate_values_pool)

        generation = 0
        for length in range(min_len, max_len):
            # we can set this without locking, since noone else writes (main
            # driver is single-threaded) and every potential worker will just
            # read-access this value.
            generation = length + 1
            fuzzing_mode = fuzzing_schedule[length]

            # extend sequences with new request templates
            seq_collection, extended_requests = extend(seq_collection, fuzzing_requests, global_lock)
            print(f"{formatting.timestamp()}: Generation: {generation} ")

            logger.write_to_main(
                f"{formatting.timestamp()}: Generation: {generation} / "
                f"Sequences Collection Size: {len(seq_collection)} "
                f"(After {fuzzing_schedule[length]} Extend)"
            )

            # render templates
            try:
                seq_collection_exhausted = False
                seq_collection = render(seq_collection, fuzzing_pool, checkers, generation, global_lock)

            except TimeOutException:
                logger.write_to_main("Timed out...")
                timeout_reached = True
                seq_collection_exhausted = True
                # Increase fuzzing generation after timeout because the code
                # that does it would have never been reached. This is done so
                # the previous generation's test summary is logged correctly.
                Monitor().current_fuzzing_generation += 1

            except ExhaustSeqCollectionException:
                logger.write_to_main("Exhausted collection...")
                seq_collection = []
                seq_collection_exhausted = True

            logger.write_to_main(
                f"{formatting.timestamp()}: Generation: {generation} / "
                f"Sequences Collection Size: {len(seq_collection)} "
                f"(After {fuzzing_schedule[length]} Render)"
            )

            # saving latest state
            saver.save(GrammarRequestCollection(), seq_collection, fuzzing_requests, Monitor(), generation)

            # Print stats for iteration of the current generation
            logger.print_generation_stats(GrammarRequestCollection(), Monitor(), global_lock)

            # Special handling for test modes
            if fuzzing_mode == 'directed-smoke-test' or fuzzing_mode == 'all-renderings-test':
                # When in a test mode, remove the extended requests from fuzzing_requests,
                # because the goal is to test each request once.
                remaining_requests = [req for req in fuzzing_requests if req not in extended_requests ]
                fuzzing_requests = FuzzingRequestCollection()
                fuzzing_requests.set_all_requests(remaining_requests)

                logger.write_to_main(f"Test mode: extended requests = {len(extended_requests)},"
                                     f"remaining requests = {len(remaining_requests)}.")

                # Print an error message if finished and there are remaining requests that were not used.
                if not extended_requests:
                    for request in fuzzing_requests:
                        logger.write_to_main(f"\nSkipping request {request.method} {request.endpoint}\n"
                                             f"Could not render request because of missing dependencies.", True)

            num_total_sequences += len(seq_collection)

            logger.print_request_rendering_stats(
                GrammarRequestCollection().candidate_values_pool,
                fuzzing_requests,
                Monitor(),
                Monitor().num_fully_rendered_requests(fuzzing_requests.all_requests),
                generation,
                global_lock
            )

            if timeout_reached or seq_collection_exhausted:
                if timeout_reached:
                    should_stop = True
                break
        logger.write_to_main("--\n")

    if fuzzing_pool is not None:
        fuzzing_pool.close()
        fuzzing_pool.join()

    return num_total_sequences

def replay_sequence_from_log(replay_log_filename, token_refresh_cmd):
    """ Replays a sequence of requests from a properly formed log file

    @param replay_log_filename: The log's filename
    @type  replay_log_filename: Str
    @param token_refresh_cmd: The command to create an authorization token
    @type  token_refresh_cmd: Str

    @return: None
    @rtype : None

    """

    log_file = open(replay_log_filename, "r")
    file_lines = log_file.readlines()

    send_data = []
    for line in file_lines:
        line = line.strip()
        # Check for comment or empty line
        if line:
            if line.startswith(logger.REPLAY_REQUEST_INDICATOR):
                # Clean up the request string before continuing
                line = line.lstrip(logger.REPLAY_REQUEST_INDICATOR)
                line = line.rstrip('\n')
                line = line.replace('\\r', '\r')
                line = line.replace('\\n', '\n')
                if not Settings().host:
                    # Extract hostname from request
                    hostname = get_hostname_from_line(line)
                    if hostname is None:
                        raise Exception("Host not found in request. The replay log may be corrupted.")
                    Settings().set_hostname(hostname)

                # Append the request data to the list
                # None is for the parser, which does not currently run during replays.
                send_data.append(sequences.SentRequestData(line, None))
            elif line.startswith(logger.BUG_LOG_NOTIFICATION_ICON):
                line = line.lstrip(logger.BUG_LOG_NOTIFICATION_ICON)
                if line.startswith('producer_timing_delay'):
                    if send_data:
                        # Add the producer timing delay to the most recent request data
                        send_data[-1].producer_timing_delay = int(line.lstrip('producer_timing_delay '))
                if line.startswith('max_async_wait_time'):
                    if send_data:
                        # Add the max async wait time to the most recent request data
                        send_data[-1].max_async_wait_time = int(line.lstrip('max_async_wait_time '))

    sequence = sequences.Sequence()
    sequence.set_sent_requests_for_replay(send_data)

    if token_refresh_cmd:
        # Set the authorization tokens in the data
        execute_token_refresh_cmd(token_refresh_cmd)

    # Send the requests
    sequence.replay_sequence()
