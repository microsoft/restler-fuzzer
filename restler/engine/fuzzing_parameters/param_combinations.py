# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import print_function

import itertools
import json

import engine.primitives as primitives
import utils.logger as logger
from restler_settings import Settings
from engine.fuzzing_parameters.fuzzing_utils import *
from engine.fuzzing_parameters.request_params import *


def get_param_list_combinations(param_list, max_combinations, choose_n):
    """ Generator that takes the specified list and returns all combinations of the elements.
    """
    def generate_combinations():
        param_count = len(param_list)
        if choose_n is None:
            combination_size_range = range(1, param_count + 2)
        elif choose_n == "max":
            combination_size_range = range(param_count + 1, param_count + 2)
        else:
            c = int(choose_n)
            if 0 < c <= param_count:
                combination_size_range = range(c + 1, c + 2)
            else:
                raise Exception(f"Invalid choose_n specified: {choose_n}, there are only {param_count} parameters.")

        for i in combination_size_range:
            num_items = i - 1
            combinations_num_i = itertools.combinations(param_list, num_items)
            for new_param_list in combinations_num_i:
                new_param_list = list(new_param_list)
                yield new_param_list

    return itertools.islice(generate_combinations(), 0, max_combinations)


def filter_required(p_list, required_val=True):
    """ Given a list of parameters, returns a list
        containing only the required parameters.
    """
    rp = []
    for p in p_list:
        if p.is_required == required_val:
            rp.append(p)
    return rp


def get_max_combinations(param_combinations_setting):
    if 'max_combinations' in param_combinations_setting:
        max_combinations = param_combinations_setting['max_combinations']
    else:
        max_combinations = Settings().max_combinations
    return max_combinations


def get_choose_n(param_combinations_setting):
    if 'choose_n' in param_combinations_setting:
        return param_combinations_setting['choose_n']
    else:
        return None


def get_param_kind(param_combinations_setting):
    if 'param_kind' in param_combinations_setting:
        param_kind = param_combinations_setting['param_kind']
    else:
        param_kind = "all"
    return param_kind


def get_param_combinations(req, param_combinations_setting, param_list, param_type):
    """
    param_type is either "header" or "query"
    """
    if param_type not in ["header", "query"]:
        raise Exception(f"Invalid param_type: {param_type}.  Specify 'header' or 'query'.")

    param_kind = get_param_kind(param_combinations_setting)

    max_combinations = get_max_combinations(param_combinations_setting)
    choose_n = get_choose_n(param_combinations_setting)
    if param_kind == "all":
        # Send combinations of all available parameters.
        for x in get_param_list_combinations(param_list, max_combinations, choose_n):
            yield x
    elif param_kind == "required":
        # Only send required parameter combinations, and omit optional parameters.
        required_params_list = filter_required(param_list)
        for x in get_param_list_combinations(required_params_list, max_combinations, choose_n):
            yield x
    elif param_kind == "optional":
        # Send required parameters, and additionally send combinations
        # of optional parameters.
        required_params_list = filter_required(param_list)
        optional_params_list = filter_required(param_list, required_val=False)

        optional_param_combinations = get_param_list_combinations(optional_params_list, max_combinations, choose_n)

        for opc in optional_param_combinations:
            yield required_params_list + opc
    else:
        raise Exception("Invalid setting for parameter combinations:"
                        f"{param_type}_{param_combinations_setting}.  \
                        Valid values are: required, optional, all.")


class JsonBodySchemaFuzzerBase:
    """ Base Class for generating structural json body combinations.

        The functions named 'fuzz_<schema member>' correspond to schema members defined in 'request_params.py'.
        When 'schema.get_fuzzing_pool' is invoked, 'get_fuzzing_pool' will be invoked on each node, which
        will, in turn, invoke the 'fuzz_<_>' functions defined below (or overridden in a subclass).
        The 'fuzz_<_>' do not generate any combinations, and should by default return a fuzzing pool
        with one schema, equal to the seed.
        When inheriting from this base class, override the desired 'fuzz_<member kind>' function to
        generate more than one fuzzed schema.
    """

    def __init__(self):
        """ Initialize the body schema fuzzer

        @return: None
        @rtype:  None

        """
        self._max_combination = 1000
        self._max_propagation = 1000
        self._filter_fn = None

    def set_filter_fn(self, filter_fn):
        self._filter_fn = filter_fn

    def _get_propagation_product(self, children, bound):
        """ Return the product sets for propagation

        @param children: A list of children (variants)
        @type  children: List
        @param bound: Max num of combination
        @type  bound: Int

        @return: A list of product
        @rtype:  List

        """
        return get_product_linear_fair(children, bound)

    def run(self, schema_seed, config={}):
        """ Fuzz the seed body schema

        @param schema_seed: Seed body schema to fuzz
        @type  schema_seed: BodySchema
        @param config: Run-time configuration
        @type  config: Dict

        @return: A list of body schema variants
        @rtype:  List [ParamObject]

        """
        pool = schema_seed.get_fuzzing_pool(self, config)
        if len(pool) <= self._max_combination:
            return pool
        else:
            return pool[:self._max_combination]

    def _fuzz_member(self, param_member, fuzzed_value):
        """ Fuzz a ParamMember node
        @param param_member: Current fuzzing node
        @type  param_member: ParamMember
        @param fuzzed_value: List of value variants (of the member)
        @type  fuzzed_value: List [ParamValue]
        @return: A list of member variants
        @rtype:  List [ParamMember]
        """
        # If the member has children that have already been included, do not filter it out
        has_children = False
        for x in fuzzed_value:
            if isinstance(x, ParamObject) and x.members:
                has_children = True
                break
        if has_children:
            include_param_member = True
        else:
            include_param_member = self._filter_fn is None or self._filter_fn(param_member)
        if not include_param_member:
            return []

        fuzzed_members = []
        # compose
        for new_value in fuzzed_value:
            new_member_properties = ParamProperties(is_required=param_member.is_required,
                                                    is_readonly=param_member.is_readonly)
            new_member = ParamMember(param_member.name, new_value, param_properties=new_member_properties)
            new_member.meta_copy(param_member)
            fuzzed_members.append(new_member)

        return fuzzed_members

    def _fuzz_object(self, param_object, fuzzed_members):
        """ Fuzz a ParamObject node (with members)

        @param param_object: Current fuzzing node
        @type  param_object: ParamObject
        @param fuzzed_members: List of members variants (of the object)
        @type  fuzzed_members: List [ [ParamMember] ]

        @return: A list of object variants
        @rtype:  List [ParamObject]

        """
        # structurally fuzz the object node
        structurally_fuzzed_fuzzed_members = self._fuzz_members_in_object(
            fuzzed_members
        )

        # Each element in structurally_fuzzed_fuzzed_members is a list of
        # member variants, whose products define an object.
        members_pool = []
        for new_fuzzed_members in structurally_fuzzed_fuzzed_members:
            # new_fuzzed_members =
            #   [ member1_variants, member2_variants, member3_variants ]
            members_pool += self._get_propagation_product(
                new_fuzzed_members, self._max_propagation
            )

        # shuffle
        self._apply_shuffle_propagation(members_pool)

        # compose
        fuzzed_objects = []
        for members in members_pool:
            new_object = ParamObject(members)
            new_object.meta_copy(param_object)
            fuzzed_objects.append(new_object)

        return fuzzed_objects

    def _fuzz_object_leaf(self, param_object):
        """ Fuzz a ParamObject node (without members)

        @param param_object: Current fuzzing node
        @type  param_object: ParamObject

        @return: A list of object variants
        @rtype:  List [ParamObject]

        """
        return [param_object]

    def _apply_shuffle_propagation(self, values_pool):
        """ Shuffle (re-order) the values in the list.  No shuffling is done by default.
        """
        pass

    def _fuzz_array(self, param_array, fuzzed_values):
        """ Fuzz a ParamArray node

        @param param_array: Current fuzzing node
        @type  param_array: ParamArray
        @param fuzzed_values: List of values variants (of the array)
        @type  fuzzed_values: List [ [ParamValue] ]

        @return: A list of array variants
        @rtype:  List [ParamArray]

        """
        # structurally fuzz the array node
        structurally_fuzzed_fuzzed_values = self._fuzz_values_in_array(
            fuzzed_values
        )

        # Each element in structurally_fuzzed_fuzzed_values is a list of value
        # variants, whose products define an array.
        values_pool = []
        for new_fuzzed_values in structurally_fuzzed_fuzzed_values:
            # new_fuzzed_values =
            #   [ value1_variants, value2_variants, value3_variants ]
            values_pool += self._get_propagation_product(
                new_fuzzed_values, self._max_propagation
            )

        # shuffle
        self._apply_shuffle_propagation(values_pool)

        # compose
        fuzzed_array = []
        for values in values_pool:
            new_array = ParamArray(values)
            new_array.meta_copy(param_array)
            fuzzed_array.append(new_array)

        return fuzzed_array

    def _fuzz_string(self, param_string):
        """ Fuzz a ParamString node

        @param param_string: Current fuzzing node
        @type  param_string: ParamString

        @return: A list of string variants
        @rtype:  List [ParamString]

        """
        return [param_string]

    def _fuzz_number(self, param_number):
        """ Fuzz a ParamNumber node

        @param param_number: Current fuzzing node
        @type  param_number: ParamNumber

        @return: A list of number variants
        @rtype:  List [ParamNumber]

        """
        return [param_number]

    def _fuzz_boolean(self, param_boolean):
        """ Fuzz a ParamBoolean node

        @param param_number: Current fuzzing node
        @type: param_number: ParamBoolean

        @return: A lsit of Boolean variants
        @rtype:  List [ParamBoolean]

        """
        return [param_boolean]

    def _fuzz_enum(self, param_enum):
        """ Fuzz a ParamEnum node

        @param param_enum: Current fuzzing node
        @type  param_enum: ParamEnum

        @return: A list of enum variants
        @rtype:  List [ParamEnum]

        """
        return [param_enum]

    def _fuzz_members_in_object(self, fuzzed_members):
        """ Fuzz members in a ParamObject node

        @param fuzzed_members: A list of member variants (length == object size)
        @type  fuzzed_members: List [ [ParamMember] ]

        @return: A list of variants of member variants
        @rtype:  List [ [ [ParamMember] ] ]

        """
        # fuzzed_members =
        #   [ member1_variants, member2_variants, ..., memberN_variants ]
        return [fuzzed_members]

    def _fuzz_values_in_array(self, fuzzed_values):
        """ Fuzz values in a ParamArray node

        @param fuzzed_values: A list of value variants (length == array size)
        @type  fuzzed_values: List [ [ParamValue] ]

        @return: A list of variants of value variants
        @rtype:  List [ [ [ParamValue] ] ]

        """
        # fuzzed_values =
        #   [ value1_variants, value2_variants, ..., valueN_variants ]
        return [fuzzed_values]


class JsonBodyPropertyCombinations(JsonBodySchemaFuzzerBase):
    """
    Generates combinations of JSON body properties.
    """
    def __init__(self):
        JsonBodySchemaFuzzerBase.__init__(self)

    def _generate_member_combinations(self, fuzzed_items, max_combinations=None):
        """ Compute combinations of the fuzzed items, which are
            properties.
            Supports returning n-wise combinations up to 'max_combinations'.
        """
        member_combinations = get_param_list_combinations(fuzzed_items, max_combinations, choose_n=None)
        combination_list = list(member_combinations)
        return combination_list

    def _fuzz_members_in_object(self, fuzzed_members):
        return self._generate_member_combinations(fuzzed_members)


def get_body_param_combinations(req, param_combinations_setting, body_schema):
    """
    Gets the body parameter combinations according to the specified setting.

    TODO: not fully implemented.  Currently, this function supports filtering
    the schema only.  The rest of the 'param_combination_setting' properties
    are not used.
    """
    max_combinations = get_max_combinations(param_combinations_setting)
    param_kind = get_param_kind(param_combinations_setting)

    schema_generator = JsonBodySchemaFuzzerBase()

    # Always filter out readonly parameters
    if param_kind == "optional":
        schema_generator.set_filter_fn(lambda x: x.is_required and not x.is_readonly)
    else:
        schema_generator.set_filter_fn(lambda x: not x.is_readonly)

    schema_pool = schema_generator.run(body_schema)
    for new_schema in schema_pool:
        yield new_schema

