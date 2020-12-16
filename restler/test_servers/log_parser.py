# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Module includes classes used to parse logs for testing purposes """
from test_servers.parsed_requests import *

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
        if self._seq_list != other._seq_list:
            print("Fuzzing sequence lists do not match.")
            return False
        return True

    def _parse(self, max_seq):
        """ Parses the fuzzing log to populate the seq list

        @param max_seq: The maximum number of sequences to parse. -1 means no max.
        @type  max_seq: Int
        @return: None
        @rtype : None

        """
        with open(self._path, 'r') as file:
            try:
                line = file.readline()
                while line:
                    # Find the start of a new sequence
                    if GENERATION in line and RENDERING_SEQUENCE in line:
                        # extract the sequence length
                        num_reqs = int(line.split(GENERATION)[1].split(': ')[0])
                        seq_num = int(line.split(RENDERING_SEQUENCE)[1])

                        if max_seq > 0 and seq_num > max_seq:
                            return

                        seq = ParsedSequence([])
                        # Add each request in the sequence to the sequence object
                        for i in range(num_reqs):
                            while line and SENDING not in line:
                                line = file.readline()
                                if REPLAY_START in line:
                                    self._skip_replay(file)

                            seq += self._get_request(line, True)
                            line = file.readline()

                        # Extend the list of sequences in this log
                        self._seq_list += [seq]
                    elif CHECKER_START in line:
                        self._handle_checker(seq, line, file)
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
        if self._req_set != other._req_set:
            print("GC request lists do not match.")
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
