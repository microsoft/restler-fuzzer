# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Trace database for REST API request/response sequences. """

from restler_settings import Settings
from utils.logging.ndjson_serializer import *
import time
import queue
import threading
import uuid
import utils.import_utilities as import_utilities

DEFAULT_ORIGIN = 'main_driver'

# Thread local storage for tracking the current sequence and request
threadLocal = threading.local()

def _get_trace():
    """Gets the thread-local trace property for the current thread."""
    if not hasattr(threadLocal, 'trace'):
        threadLocal.trace = {}
        threadLocal.thread_id = threading.get_ident() # for debugging
    return threadLocal.trace

class SequenceTracker:
    @staticmethod
    def get_trace_log():
        trace = _get_trace()
        if 'sequence' not in trace:
            return None
        return trace['sequence']

    @staticmethod
    def get_sequence_id():
        tls_trace_log = SequenceTracker.get_trace_log()
        if tls_trace_log is None:
            return None
        return tls_trace_log.sequence_id


    @staticmethod
    def initialize_sequence_trace(combination_id, tags={}):
        """Requests and responses are logged separately, but metadata about sequences is tracked and logged
        with each request and response. This function initializes the metadata for the current sequence.
        """
        trace = _get_trace()
        if 'sequence' in trace:
            if trace['sequence'].combination_id != combination_id:
                print("WARNING: There is already a sequence executing. Continuing with different sequence.")
            else:
                print("WARNING: There is already a sequence executing. Continuing with the same sequence.")
        unique_sequence_id=str(uuid.uuid4())
        trace['sequence'] = RequestTraceLog(combination_id=combination_id,
                                            sequence_id=unique_sequence_id,
                                            sequence_tags=tags)

    @staticmethod
    def initialize_request_trace(request_id=None, combination_id=None, tags={}):
        """Initialize trace log for the request."""
        trace = _get_trace()

        if combination_id is None:
            raise Exception("ERROR: Combination ID must be specified")
        if 'sequence' not in trace:
            raise Exception("ERROR: Sequence trace must be initialized before initializing the request trace.")

        sequence_trace = trace['sequence']
        if sequence_trace.combination_id != combination_id:
            raise Exception("ERROR: Combination ID must match Combination ID of initialized trace log.")

        sequence_trace.request_id = request_id
        sequence_trace.tags = tags

    @staticmethod
    def clear_sequence_trace():
        trace = _get_trace()
        if 'sequence' in trace:
            del trace['sequence']

    @staticmethod
    def clear_request_trace(combination_id):
        trace = _get_trace()
        if combination_id is None:
            raise Exception("ERROR: Sequence ID must be specified.")

        sequence_trace = trace['sequence']
        if sequence_trace.combination_id != combination_id:
            raise Exception("ERROR: Sequence ID must match sequence ID of initialized trace log.")
        sequence_trace.request_id = None
        sequence_trace.tags = None

    @staticmethod
    def set_origin(origin):
        trace = _get_trace()
        trace['origin'] = origin

    @staticmethod
    def clear_origin():
        trace = _get_trace()
        trace['origin'] = DEFAULT_ORIGIN

    @staticmethod
    def get_origin():
        trace = _get_trace()
        if 'origin' not in trace:
            return None
        return trace['origin']


class TraceDatabase:
    """ This class enables structured storage and retrieval of RESTler logs.
        The serialization format is pluggable and may be specified by the user (currently,
        only one logger at a time is supported).
        The default format is newline-delimited json.
    """
    def __init__(self, storage_writer):
        self.storage_writer = storage_writer
        self._log_queue = queue.SimpleQueue()
        self._finished = False

    @property
    def trace(self):
        return _get_trace()

    def log_request_response(self, request=None, response=None,  tags={}, timestamp=None):
        if request is None and response is None:
            raise Exception("ERROR: Request or response must be specified.")
        try:
            tls_trace_log = SequenceTracker.get_trace_log()
            if tls_trace_log is None:
                # Logging requests outside of sequence context (e.g. GC or checker requests
                # that are not part of a sequence)
                trace_log = RequestTraceLog()
            else:
                trace_log = RequestTraceLog(request_id=tls_trace_log.request_id,
                                            sequence_id=tls_trace_log.sequence_id,
                                            combination_id=tls_trace_log.combination_id,
                                            sequence_tags=tls_trace_log.sequence_tags,
                                            tags=tls_trace_log.tags)
            trace_log.origin = SequenceTracker.get_origin()
            if request:
                trace_log.request = request
                if timestamp is not None:
                    trace_log.sent_timestamp = timestamp
            if response:
                trace_log.response = response
                if timestamp is not None:
                    trace_log.received_timestamp = timestamp
            if tags:
                trace_log.tags.update(tags)
            if 'origin' not in trace_log.tags and trace_log.origin is None:
                raise Exception(f"Missing origin: request: {trace_log.request_id}, sequence: {trace_log.sequence_id}")
            self.log(trace_log.to_dict())
        except Exception as error:
            # print the callstack
            import traceback
            traceback.print_exc()
            print(f"Warning: Exception logging request/response: {error}")
            pass

    def log(self, message):
        if self._finished:
            raise Exception("ERROR: log() should not be called after finish().")
        self._log_queue.put(message)

    def log_queue_empty(self):
        return self._log_queue.empty()

    def finish(self):
        if self._finished:
            raise Exception("ERROR: finish() should only be called once.")
        self._finished = True
        self._log_queue.put(None)

    def save_log_message(self):
        """Takes a message off the queue and saves it using the specified serializer.
            If fewer messages are available, it will save all available messages.
        """
        message = self._log_queue.get()
        if message is None:
            # End of tracing signal
            return
        self.storage_writer.save(message)

    def load_trace_data(self):
        self.storage_writer.load()

    def normalize_trace_data(self):
        """TODO: this is currently a placeholder."""
        self.storage_writer.normalize()

# Trace database global variable
_db = None

def set_up_trace_database(root_dir_path):
    from utils.logger import EXPERIMENT_DIR

    def set_up_custom_serializer(serializer_file_path):
        """ Set up a custom serializer for the trace database.
        The custom serializer must inherit from the 'TraceLogWriterBase' class, and accept one argument,
        which is the settings object specified by the user in the engine settings.
        """
        obj = None
        custom_serializer = import_utilities.import_subclass(serializer_file_path, TraceLogWriterBase)
        if custom_serializer is not None:
            # Instantiate using the settings object specified by the user.
            obj = custom_serializer(Settings().trace_db_serializer_settings)
        return obj

    global _db
    if _db is not None:
        raise Exception("Trace database already initialized")

    serializer_file_path = Settings().trace_db_custom_serializer_file_path
    if serializer_file_path is not None:
        storage_writer = set_up_custom_serializer(serializer_file_path)
    else:
        storage_writer = JsonTraceLogWriter(root_dir_path)
    _db = TraceDatabase(storage_writer)
    return _db

def DB():
    """Gets the trace database instance"""
    return _db

class TraceDatabaseThread(threading.Thread):
    """ Trace database thread class. """
    def __init__(self, trace_db):
        """
        @param trace_db: The trace database.
        @type  trace_db: TraceDatabase class object.

        @return: None
        @rtype : None

        """
        threading.Thread.__init__(self)

        self._trace_db = trace_db
        self.stop_event = threading.Event()

    def run(self):
        """ Thread entrance - periodically write to the trace database.

        @return: None
        @rtype : None

        """
        while not self.stop_event.is_set():
            self._trace_db.save_log_message()

    def finish(self, max_cleanup_time):
        """ Begins the final cleanup

        @param max_cleanup_time: The amount of time to continue doing work
                                 after this function call
        @type  max_cleanup_time: Integer
        @return: None
        @rtype : None

        """
        cleanup_start_time = time.time()
        elapsed_time = 0
        while not self._trace_db.log_queue_empty() and elapsed_time < max_cleanup_time:
            time.sleep(1)
            elapsed_time = time.time() - cleanup_start_time

        self.stop_event.set()
        # If the worker is waiting for new items on the queue, this will unblock it.
        self._trace_db.finish()

