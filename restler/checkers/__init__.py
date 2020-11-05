# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# The ordering of these checkers is expected to remain consistent.
# If a new checker is added or a new ordering is deemed necessary,
# the unit tests and baseline logs will need to be updated as well.
from checkers.leakage_rule_checker import *
from checkers.resource_hierarchy_checker import *
from checkers.use_after_free_checker import *
from checkers.namespace_rule_checker import *
from checkers.invalid_dynamic_object_checker import *
from checkers.payload_body_checker import *
from checkers.examples_checker import *