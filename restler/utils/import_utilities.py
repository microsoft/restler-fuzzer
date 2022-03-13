# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""  Primitive types supported by restler. """
from __future__ import print_function
import sys
import os
import time
import datetime
import uuid
import itertools
import importlib
import importlib.util
import types
import shutil

def load_module(name, module_file_path):
    spec = importlib.util.spec_from_file_location(name, module_file_path)
    module_to_load = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_to_load)

def import_attr(module_file_path, attr_name):
    file_name = os.path.basename(module_file_path)
    module_name = file_name.replace(".py", "")

    # Import the object
    sys.path.append(os.path.dirname(module_file_path))
    imported_module = importlib.import_module(module_name)
    imported_attr = getattr(imported_module, attr_name)

    return imported_attr

