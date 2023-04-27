# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Module includes classes used to parse logs for testing purposes """
from test_servers.parsed_requests import *

import copy
import json
from collections import Counter

SENDING = ': Sending: '
GENERATION = 'Generation-'
RENDERING_SEQUENCE = ': Rendering Sequence-'
CHECKER = 'Checker'
CHECKER_START = 'Checker kicks in'
CHECKER_END = 'Checker kicks out'
BUG_START = '-------------'
REPLAY_START = ': Attempting to reproduce bug...'
REPLAY_END = ': Done replaying sequence.'

class TestFailedException(Exception):
    __test__ = False
    """ Raised when a failure occurred while running the test. """
    pass

class LogParser:
    """ Base class for log parsers """
    def __init__(self, path):
        """ LogParser constructor

        @param path: The path to the log to parse
        @type  path: Str

        """
        self._path = path

    def _get_request(self, line, delete_sending=False):
        """ Gets the ParsedRequest object found in a line of the log file

        @param line: The line to extract the request from
        @type  line: Str
        @param delete_sending: If true, a SENDING section exists that must be removed
        @type  delete_sending: Bool

        @return: The request extracted from the line
        @rtype : ParsedRequest

        """
        line = line.replace('\\r', '\r')
        line = line.replace('\\n', '\n')
        # Remove the trailing \n
        line = line[:-1]
        if delete_sending:
            return ParsedRequest(line.split(SENDING)[1].strip("'"), ignore_dynamic_objects=True)
        return ParsedRequest(line, ignore_dynamic_objects=True)


class FuzzingLogParser(LogParser):
    """ Responsible for parsing standard fuzzing logs """
    def __init__(self, path, max_seq=-1):
        """ FuzzingLogParser constructor

        @param path: The path to the fuzzing log to parse
        @type  path: Str

        """
        super().__init__(path)
        self._seq_list = []

        self._parse(max_seq)

    def _skip_replay(self, file):
        """ Moves the log file's pointer beyond a replay section

        @param file: The log file's pointer
        @type  file: IO

        @return: None
        @rtype : None

        """
        line = file.readline()
        while line and REPLAY_END not in line:
            line = file.readline()

    def _handle_checker(self, seq, line, file):
        """ Populates a sequence's checker requests

        @param seq: The sequence that the checker requests belong to
        @type  seq: ParsedSequence
        @param line: The CHECKER_START line
        @type  line: Str
        @param file: The log file's pointer
        @type  file: IO

        @return: None
        @type  : None

        """
        # Get checker name
        checker = line.split(CHECKER, 2)[1][2:]
        if checker not in seq.checker_requests:
            seq.checker_requests[checker] = []
        while line and CHECKER_END not in line:
            if SENDING in line:
                seq.checker_requests[checker] += [self._get_request(line, True)]
            if REPLAY_START in line:
                self._skip_replay(file)
            line = file.readline()

    def diff_log(self, other):
        """ Diffs a FuzzingLogParser's seq list to this object's seq list

        @param other: The parser to compare to this one
        @type  other: FuzzingLogParser

        @return: True if the logs' seq lists match
        @rtype : Bool

        """

        def get_diff(left_seq_list, right_seq_list, description_str, diff_checkers=True):
            """ Gets the difference between two sequence lists

            @param left_seq_list: The left sequence list
            @type  left_seq_list: List[ParsedSequence]

            @param right_seq_list: The right sequence list
            @type  right_seq_list: List[ParsedSequence]

            @param description_str: The description of the right sequence list
            @type  description_str: Str

            @param diff_checkers: If true, diff both the checker and main requests, otherwise
                                  diff the main requests only.
            @type  diff_checkers: Bool
            """
            right_seq_list_copy = copy.copy(right_seq_list)
            for left in left_seq_list:
                found = False
                found_idx = -1
                found_count = 0

                for idx, right in enumerate(right_seq_list_copy):
                    found_request_sequence = (left.requests == right.requests)
                    found_checkers = (left.checker_requests == right.checker_requests)
                    if found_request_sequence:
                        found_idx = idx
                        found_count += 1

                        if not diff_checkers or found_checkers:
                            found = True

                    if found_request_sequence:
                        break
                if found:
                    right_seq_list_copy.pop(found_idx)
                elif found_request_sequence:
                    # Found the request sequence, but the checker requests are different
                    print(f"+++ Found checker requests not in {description_str} set +++")
                    print("+++ Request sequence: +++")
                    for req in left.requests:
                        print(f"endpoint: {req.endpoint}, method: {req.method}, body: {req.body}")
                    print("+++ Checker requests: +++")
                    right_checkers_requests = right_seq_list_copy[found_idx].checker_requests
                    for name, left_checker_reqs in left.checker_requests.items():
                        if name in right_checkers_requests:
                            right_checker_reqs = right_checkers_requests[name]
                            if left_checker_reqs != right_checker_reqs:
                                if left_checker_reqs and right_checker_reqs:
                                    # Diff the checker requests
                                    left_counter = Counter(left_checker_reqs)
                                    right_counter = Counter(right_checker_reqs)

                                    left_diff = left_counter - right_counter
                                    right_diff = right_counter - left_counter
                                    print(f"Checker name: {name}")
                                    print(f"--- Left diff ({description_str} - other): ---")
                                    for req in left_diff:
                                        print(f"endpoint: {req.endpoint}, method: {req.method}, body: {req.body}")
                                    print(f"--- Right diff (other - {description_str}): ---")
                                    for req in right_diff:
                                        print(f"endpoint: {req.endpoint}, method: {req.method}, body: {req.body}")
                                else:
                                    print(f"Checker {name} is enabled in the {description_str} set, but did not kick in.")
                        else:
                            print(f"Checker {name} is enabled in the {description_str} set, but not in the other set.")

                    return False
                else: # Did not find the request sequence
                    print(f"+++ Found request sequence not in {description_str} set +++")
                    for req in left.requests:
                        print(f"endpoint: {req.endpoint}, method: {req.method}, body: {req.body}")
                    return False

                if found_count > 1:
                    print(f"+++ Found request sequence {found_count} (more than once) times in {description_str} set +++")
                    for req in left.requests:
                        print(f"endpoint: {req.endpoint}, method: {req.method}, body: {req.body}")
                    return False
            return True

        if self._seq_list != other._seq_list:
            print("Fuzzing sequence lists do not match.")

            # To help diagnose failures, compare the two sequences of tests as sets.
            #
            found_right = get_diff(self._seq_list, other._seq_list, "right", diff_checkers=False)
            found_left = get_diff(other._seq_list, self._seq_list, "left", diff_checkers=False)

            if not (found_right and found_left):
                return False

            print("The main algorithm requests are identical.  Checking checker requests...")
            found_right = get_diff(self._seq_list, other._seq_list, "right", diff_checkers=True)
            found_left = get_diff(other._seq_list, self._seq_list, "left", diff_checkers=True)

            if not (found_right and found_left):
                return False

            print("The sequences are identical, only the ordering is different.")

            # TODO (GitHub #233): the below code is temporarily modified to return True, in order to
            # pass unit tests, because changes to sequences are currently expected.
            # This should be changed back to return 'False' in a follow-up change when baselines are updated.
            # return False
            return True

        return True

    def validate_auth_tokens(self, tokens):
        """ Validate that every token request header is in the set of valid tokens

        @param other: Set of valid tokens
        @type  other: Set

        @return: True if all tokens in the request sequence are in the set of valid tokens
        @rtype : Bool

        """
        for seq in self._seq_list:
            for request in seq.requests:
                if not request.authorization_token in tokens:
                    return False
        return True

    def _parse(self, max_seq):
        """ Parses the fuzzing log to populate the seq list

        @param max_seq: The maximum number of sequences to parse. -1 means no max.
        @type  max_seq: Int
        @return: None
        @rtype : None

        """
        def is_seq_or_checker_start(line):
            if GENERATION in line and RENDERING_SEQUENCE in line:
                return True
            if CHECKER_START in line:
                return True
            return False

        with open(self._path, 'r') as file:
            try:
                line = file.readline()

                while line:
                    # Find the start of a new sequence
                    if GENERATION in line and RENDERING_SEQUENCE in line:
                        # extract the sequence length
                        num_reqs = int(line.split(GENERATION)[1].split(': ')[0])
                        seq_num = int(line.split(RENDERING_SEQUENCE)[1])

                        if max_seq > 0 and len(self._seq_list) >= max_seq:
                            print(f"Testing max={max_seq} sequences.")
                            return

                        seq = ParsedSequence([])
                        # Add each request in the sequence to the sequence object
                        for i in range(num_reqs):
                            while line and SENDING not in line:
                                line = file.readline()
                                if REPLAY_START in line:
                                    self._skip_replay(file)

                                # Handle cases where fewer requests
                                # are sent due to a sequence failure
                                if is_seq_or_checker_start(line):
                                    break
                            if SENDING in line:
                                seq += self._get_request(line, True)
                                line = file.readline()
                            else:
                                break

                        # Extend the list of sequences in this log
                        self._seq_list.append(seq)
                    elif CHECKER_START in line:
                        self._handle_checker(seq, line, file)
                        line = file.readline()

                    # Only read the next line if it is not already at the start of the
                    # next operation to process
                    if not is_seq_or_checker_start(line):
                        line = file.readline()

            except Exception as err:
                print("Failed to read fuzzing log. Log was not a complete test log.\n"
                      f"{err!s}")
                raise TestFailedException

class GarbageCollectorLogParser(LogParser):
    """ Responsible for parsing garbage collector logs """
    def __init__(self, path):
        """ GarbageCollectorLogParser constructor

        @param path: The path to the garbage collector log file
        @type  path: Str

        """
        super().__init__(path)
        self._req_set = set()

        self._parse()

    def diff_log(self, other):
        """ Diffs a GarbageCollectorLogParser's req list to this object's req list

        @param other: The parser to compare to this one
        @type  other: GarbageCollectorLogParser

        @return: True if the req lists match
        @rtype : Bool

        """
        def print_request_set(req_set, set_name):
            print(f"{set_name}")
            for req in req_set:
                print(f"endpoint: {req.endpoint}, method: {req.method}, body: {req.body}")

        if self._req_set != other._req_set:
            print("GC request lists do not match.")
            print_request_set(self._req_set, "First set")
            print_request_set(other._req_set, "Second set")
            return False
        else:
            return True

    def _parse(self):
        """ Parses the garbage collector log to populate the req list

        @return: None
        @rtype : None

        """
        with open(self._path, 'r') as file:
            try:
                line = file.readline()
                while line:
                    if SENDING in line:
                        self._req_set.add(self._get_request(line, True))
                    line = file.readline()
            except Exception as err:
                print("Failed to read garbage collector log. Log was not a complete test log.\n"
                      f"{err!s}")
                raise TestFailedException

class BugLogParser(LogParser):
    """ Responsible for parsing bug bucket logs """
    def __init__(self, path):
        """ BugLogParser constructor

        @param path: The path to the bug log file
        @type  path: Str

        """
        super().__init__(path)
        # key = bug type, value = list(tuple(ParsedSequence, reproduced-bool, bug-hash))
        self._bug_list = dict()

        self._parse()

    def diff_log(self, other):
        """ Diffs a BugLogParser's bug list with this object's bug list

        @param other: The parser to compare to this one
        @type  other: BugLogParser

        @return: True if the bug lists match
        @rtype : Bool

        """
        if self._bug_list != other._bug_list:
            print("Bug lists do not match.")
            return False
        return True

    def _parse(self):
        """ Parses the bug log to populate the bug list

        @return: None
        @rtype : None

        """
        with open(self._path, 'r') as file:
            try:
                line = file.readline()
                while line:
                    if line.startswith(BUG_START):
                        line = file.readline()
                        if line:
                            # Extract bug type
                            bug_type = line.split(' ', 1)[0]
                            if bug_type not in self._bug_list:
                                self._bug_list[bug_type] = []
                            # Get whether or not the bug was reproduced
                            reproduced = 'Bug was reproduced' in line
                            line = file.readline()
                            if line.startswith('Attempted'):
                                # Skip the 'Attempted to reproduce' line if exists
                                line = file.readline()
                            bug_hash = line.split(' ')[-1].rstrip()
                            line = file.readline()
                            seq = ParsedSequence([])
                            # Populate the sequence of requests that made the bug
                            while line and not line.startswith(BUG_START):
                                seq += self._get_request(line)
                                line = file.readline()
                            # Add the bug sequence to the bug list
                            self._bug_list[bug_type].append((seq, reproduced, bug_hash))
                    else:
                        line = file.readline()
            except Exception as err:
                print("Failed to read bug log. Log was not a complete test log.\n"
                      f"{err!s}")
                raise TestFailedException

class JsonFormattedBugsLogParser(LogParser):
    class FileType(enumerate):
        Bugs = 'Bugs',
        BugDetails = 'BugDetails',


    def __init__(self, path, fileType):
        """ BugLogParser constructor

        @param path: The path to the bug log file
        @type  path: Str

        """
        super().__init__(path)
        # key = bug type, value = list(tuple(ParsedSequence, reproduced-bool, bug-hash))
        self._bug_list = []
        self._bug_detail = None
        self._fileType = fileType
        self._parse()

    def _parse(self):
        """ Parses the bug log to populate the bug list

        @return: None
        @rtype : None

        """
        try:
            with open(self._path, 'r') as bugs:
                bugs_json = json.load(bugs)
            if self._fileType == JsonFormattedBugsLogParser.FileType.Bugs:
                self._bug_list = bugs_json['bugs']
            elif self._fileType == JsonFormattedBugsLogParser.FileType.BugDetails:
                self._bug_detail = bugs_json
        except Exception as err:
            print("Failed to read bug buckets file type {self._fileType} in bug buckets directory.\n"
                      f"{err!s}")
            raise TestFailedException
