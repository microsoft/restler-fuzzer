import os
from utils.logging.serializer_base import *


class TraceDbTextWriter(TraceLogWriterBase):
    def __init__(self, settings):
        if 'log_file' not in settings:
            raise Exception("ERROR: 'root_directory' must be specified in the settings object")

        self.log_file_path = settings['log_file']

        if os.path.exists(self.log_file_path):
            os.remove(self.log_file_path)

    def save(self, data):
        def pretty_print_dict(d, indent=0, lines=[]):
            for key, value in d.items():
                key_str = '\t' * indent + f"{key}:"
                if isinstance(value, dict):
                    lines.append(key_str)
                    pretty_print_dict(value, indent+1, lines)
                else:
                    lines.append(key_str + ('\t' * (indent+1) + repr(value)))

        data["sent_timestamp"]=None
        data["received_timestamp"]=None
        data["sequence_id"]=None
        if "tags" in data:
            x = data["tags"]
            x["sequence_id"]=None
            data["tags"]=x
        with open(self.log_file_path, 'a') as f:
            lines=[]
            pretty_print_dict(data, lines=lines)
            f.write("\n".join(lines) + '\n')

class TraceDbTextReader(TraceLogReaderBase):
    def __init__(self, log_file_path):
        if log_file_path is None:
            raise Exception("ERROR: 'log_file_path' must be specified")

        self.log_file_path = log_file_path
        self.data = None

    def load(self):
        if self.data is None:
            self.data = []
            with open(self.log_file_path, 'r') as f:
                self.data = f.readlines()
        return self.data

