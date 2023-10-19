# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""  Primitive types supported by restler. """
from __future__ import print_function
import sys
import os
import importlib
import importlib.util
import inspect

def load_module(name, module_file_path):
    spec = importlib.util.spec_from_file_location(name, module_file_path)
    module_to_load = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_to_load)
    return module_to_load

def import_attrs(module_file_path, attr_names):
    imported_attrs = []
    try:
        file_name = os.path.basename(module_file_path)
        module_name = file_name.replace(".py", "")

        # Import the object
        sys.path.append(os.path.dirname(module_file_path))
        imported_module = load_module(module_name, module_file_path)
        for attr_name in attr_names:
            imported_attr = getattr(imported_module, attr_name, None)
            imported_attrs.append(imported_attr)
    finally:
        # Remove from path
        sys.path.pop(len(sys.path) - 1)
    return imported_attrs

def import_attr(module_file_path, attr_name):
    attrs = import_attrs(module_file_path, [attr_name])
    return attrs[0]

def import_subclass(module_file_path, base_class_name):
    subclass = None
    try:
        file_name = os.path.basename(module_file_path)
        module_name = file_name.replace(".py", "")
        # Import the object
        sys.path.append(os.path.dirname(module_file_path))
        imported_module = load_module(module_name, module_file_path)

        # Get all classes in the module
        module_classes = inspect.getmembers(imported_module, inspect.isclass)

        # Instantiate the class that inherits from the base
        for name, cls in module_classes:
            if issubclass(cls, base_class_name) and (cls.__name__ != base_class_name.__name__):
                subclass = cls
    finally:
        # Remove from path
        sys.path.pop(len(sys.path) - 1)
    return subclass

