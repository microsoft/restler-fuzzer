# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import print_function

import itertools
import json

import engine.primitives as primitives
import utils.logger as logger

def get_param_list_combinations(param_list):
    """
    Generator that takes the specified list and returns all combinations of the elements.
    """
    for i in range(1, len(param_list) + 2):
        num_items = i - 1
        combinations_num_i = itertools.combinations(param_list, num_items)
        for new_param_list in combinations_num_i:
            new_param_list = list(new_param_list)
            yield new_param_list

def get_param_combinations(req, param_combinations_setting, param_list, param_type):
    """
    param_type is either "header" or "query"
    """
    def filter_required(p_list, required_val=True):
        rp=[]
        for p in p_list:
            if p.is_required == required_val:
                rp.append(p)
        return rp
    if param_combinations_setting == "all":
        # Send combinations of all available parameters.
        for x in get_param_list_combinations(param_list):
            yield x
    elif param_combinations_setting == "required":
        # Only send required parameter combinations, and omit optional parameters.
        required_params_list = filter_required(param_list)
        for x in get_param_list_combinations(required_params_list):
            yield x
    elif param_combinations_setting == "optional":
        # Send required parameters, and additionally send combinations
        # of optional parameters.
        required_params_list = filter_required(param_list)
        optional_params_list = filter_required(param_list, required_val=False)

        optional_param_combinations = get_param_list_combinations(optional_params_list)

        for opc in optional_param_combinations:
            yield required_params_list + opc
    else:
        raise Exception("Invalid setting for parameter combinations:"
                        f"{param_type}_{param_combinations_setting}.  \
                        Valid values are: required, optional, all.")
