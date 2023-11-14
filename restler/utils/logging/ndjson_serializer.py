# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Implements serialization for REST API request/response sequences in ndjson format. """

from logging.handlers import RotatingFileHandler

import os
import glob
import time
import json
import logging

from restler_settings import Settings
from utils.logging.serializer_base import *


class CustomRotatingFileHandler(RotatingFileHandler):
    def rotation_filename(self, default_name):
        """Modify the rotation file name so the extension matches the default extension.
        Note: this function must be idempotent.
        """
        base_name, count_ext = os.path.splitext(default_name)
        base_name, type_ext = os.path.splitext(base_name)
        return base_name + count_ext + type_ext

class RequestTraceLog():
    def __init__(self, request_id=None, sequence_id=None, combination_id=None, tags={}, sequence_tags={}):
        self.request_id = request_id
        self.sequence_id = sequence_id
        self.tags = tags
        self.origin = None
        self.sequence_tags = sequence_tags
        self.combination_id = combination_id
        self.sent_timestamp = None
        self.received_timestamp = None
        self._request = None
        self._response = None
        self.request_json = None
        self.response_json = None

    @classmethod
    def from_dict(cls, log_dict):
        instance = cls()
        instance.request_id = log_dict.get('request_id')
        instance.sequence_id = log_dict.get('sequence_id')
        instance.combination_id = log_dict.get('combination_id')
        instance.sent_timestamp = log_dict.get('sent_timestamp')
        instance.received_timestamp = log_dict.get('received_timestamp')
        instance.tags = log_dict.get('tags', {})
        instance.sequence_tags = {}
        instance.request = log_dict.get('request')
        instance.response = log_dict.get('response')
        request_json = log_dict.get('request_json')
        response_json = log_dict.get('response_json')
        instance.request_json = None if request_json is None else json.loads(request_json)
        instance.response_json = None if response_json is None else json.loads(response_json)
        instance.origin = None if 'origin' not in instance.tags else instance.tags['origin']
        return instance

    def normalize(self):
        """ Normalize the request and response to a format that can be used to compare
            request sequences across two different traces.
            TODO: this is a placeholder implementation.  """
        self.sent_timestamp = None
        self.received_timestamp = None
        self.sequence_id = None
        self.tags = {}
        self.sequence_tags = {}
        return self

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            valueX = self.to_dict()
            valueY = other.to_dict()
            return valueX == valueY
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def request(self):
        return self._request

    @request.setter
    def request(self, value):
        self._request = value

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        self._response = value

    def to_dict(self):
        tags = {}
        if self.request_id is not None:
            tags["request_id"] = self.request_id
        if self.sequence_id is not None:
            tags["sequence_id"] = self.sequence_id
        if self.combination_id is not None:
            tags["combination_id"] = self.combination_id
        if self.origin is not None:
            tags["origin"] = self.origin
        tags.update(self.tags)
        tags.update(self.sequence_tags)
        return {
            'sent_timestamp': self.sent_timestamp,
            'received_timestamp': self.received_timestamp,
            'request': self.request,
            'response': self.response,
            'request_json': None if self.request_json == None else json.dumps(self.request_json),
            'response_json': None if self.request_json == None else json.dumps(self.response_json),
            'tags': tags
        }

class JsonTraceLogReader(TraceLogReaderBase):
    def __init__(self, root_directory=None, log_file_paths=[]):
        if root_directory is None and not log_file_paths:
            raise Exception("ERROR: 'root_directory' or 'log_file_paths' must be specified.")

        if root_directory is not None and log_file_paths:
            raise Exception("ERROR: 'root_directory' and 'log_file_paths' cannot both be specified.")

        self.log_file_paths = log_file_paths
        if root_directory is not None:
            self.root_directory = root_directory
            self.base_filename = os.path.join(self.root_directory, 'trace_data')
            self.ext = '.ndjson'
        else:
            self.root_directory = None
            split_path = os.path.splitext(log_file_paths[0])
            if len(split_path) < 2:
                raise Exception("ERROR: log_file_paths must have an extension")
            self.base_filename = os.path.splitext(split_path[0])[0]
            self.ext = split_path[1]

    def load(self):
        """Returns the list of RequestTraceLog objects from the trace log file."""
        if self.root_directory is not None:
            existing_files = sorted(glob.glob(f"{self.base_filename}_*{self.ext}"),
                                              key=os.path.getctime)
        else:
            existing_files = self.log_file_paths

        data = []
        for filename in existing_files:
            with open(filename, 'r') as f:
                for line in f:
                    try:
                        log_dict = json.loads(line)
                        trace_log = RequestTraceLog.from_dict(log_dict)
                        data.append(trace_log)
                    except json.JSONDecodeError:
                        print(f"Warning: Skipping malformed data in {filename}")
        return data

class JsonTraceLogWriter(TraceLogWriterBase):

    _MaxDbSize = 1024*1024*100 # = 100MB
    def __init__(self, root_directory=None, storage_limit=_MaxDbSize):
        if root_directory is None:
            raise Exception("ERROR: 'root_directory' must be specified")

        self.root_directory = root_directory
        if not os.path.exists(root_directory):
            os.makedirs(root_directory)

        log_file_path = os.path.join(self.root_directory, 'trace_data.ndjson')
        # Remember whether the trace DB already exists, since the file handler will create the file
        trace_db_exists = os.path.exists(log_file_path)

        self.logger = logging.getLogger('restler_trace_logger')
        self.logger.setLevel(logging.INFO)

        self.handler = CustomRotatingFileHandler(log_file_path, maxBytes=storage_limit, backupCount=10000)

        # If the trace DB already exists, but the user has not specified a trace DB file path, then
        # start a fresh trace DB.
        if trace_db_exists and Settings().trace_db_file_path is None:
            self.handler.doRollover()

        self.logger.addHandler(self.handler)

    def save(self, data):
        self.logger.info(json.dumps(data))


