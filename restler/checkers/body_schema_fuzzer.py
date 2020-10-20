# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import print_function

import argparse
import itertools
import json
import random

from engine.fuzzing_parameters.fuzzing_utils import *
from engine.fuzzing_parameters.request_params import *

class BodySchemaStructuralFuzzer():
    """ Body Schema Fuzzer Base Class """

    def __init__(self, LOG=print, strategy=''):
        """ Initialize the body schema fuzzer

        @param LOG: Customized log
        @type  LOG: Function

        @return: None
        @rtype:  None

        """
        # setup customized log
        self._log = LOG

        # fuzzing strategy
        self._strategy = strategy

    def run(self, schema_seed, config={}):
        """ Fuzz the seed body schema

        @param schema_seed: Seed body schema to fuzz
        @type  schema_seed: BodySchema
        @param config: Run-time configuration
        @type  config: Dict

        @return: A list of body schema variants
        @rtype:  List [ParamObject]

        """
        if not schema_seed:
            self._log('No schema seed to fuzz')
            return []

        # initialize default configuration
        self._set_default_config()

        # update customized configuration
        if 'propagate_strategy' in config:
            self._propagate_strategy = config['propagate_strategy']
        if 'max_combination' in config:
            self._max_combination = config['max_combination']
        if 'max_propagation' in config:
            self._max_propagation = config['max_propagation']
        if 'shuffle_propagation' in config:
            self._shuffle_propagation = config['shuffle_propagation']
        if 'shuffle_combination' in config:
            self._shuffle_combination = config['shuffle_combination']
        if 'random_seed' in config:
            self._random_seed = config['random_seed']

        # overwrite fuzzer-specific configuration
        self._set_fuzzer_config()

        # start fuzzing
        pool = schema_seed.get_fuzzing_pool(self, config)
        if len(pool) <= self._max_combination:
            return pool
        else:
            if self._shuffle_combination:
                random.Random(self._random_seed).shuffle(pool)
            return pool[:self._max_combination]

    def _set_default_config(self):
        """ Set default configuration

        @return: None
        @rtype:  None

        """
        self._propagate_strategy = 'EX'
        self._max_propagation = 1000
        self._max_combination = 1000
        self._shuffle_propagation = False
        self._shuffle_combination = False
        self._random_seed = 0

    def _set_fuzzer_config(self):
        """ Set fuzzer specific configuration

        @return: None
        @rtype:  None

        """
        if self._is_single_mode():
            self._propagate_strategy = 'D1'
            self._shuffle_propagation = False

        elif self._is_path_mode():
            self._propagate_strategy = 'D1'
            self._shuffle_propagation = False

        elif self._is_all_mode():
            self._propagate_strategy = 'EX'

        else:
            pass

    def _is_single_mode(self):
        """ Return if is single mode

        @return: Is single mode
        @rtype:  Bool

        """
        return self._strategy.upper() == 'SINGLE'

    def _is_path_mode(self):
        """ Return if is path mode

        @return: Is path mode
        @rtype:  Bool

        """
        return self._strategy.upper() == 'PATH'

    def _is_all_mode(self):
        """ Return if is all mode

        @return: Is all mode
        @rtype:  Bool

        """
        return self._strategy.upper() == 'ALL'

    def _fuzz_member(self, param_member, fuzzed_value):
        """ Fuzz a ParamMember node

        @param param_member: Current fuzzing node
        @type  param_member: ParamMember
        @param fuzzed_value: List of value variants (of the member)
        @type  fuzzed_value: List [ParamValue]

        @return: A list of member variants
        @rtype:  List [ParamMember]

        """
        fuzzed_members = []

        # compose
        for new_value in fuzzed_value:
            new_member = ParamMember(param_member.name, new_value)
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
        if self._shuffle_propagation:
            random.Random(self._random_seed).shuffle(members_pool)

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

        # Each element in structurall_fuzzed_fuzzed_values is a list of value
        # variants, whose products define an array.
        values_pool = []
        for new_fuzzed_values in structurally_fuzzed_fuzzed_values:
            # new_fuzzed_values =
            #   [ value1_variants, value2_variants, value3_variants ]
            values_pool += self._get_propagation_product(
                new_fuzzed_values, self._max_propagation
            )

        # shuffle
        if self._shuffle_propagation:
            random.Random(self._random_seed).shuffle(values_pool)

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

    def _get_propagation_product(self, children, bound):
        """ Return the product sets for propagation

        @param children: A list of children (variants)
        @type  children: List
        @param bound: Max num of combination
        @type  bound: Int

        @return: A list of product
        @rtype:  List

        """
        if self._propagate_strategy == 'EX':
            if bound > 0:
                return get_product_exhaust(children, bound)
            else:
                return get_product_exhaust(children, 100)

        elif self._propagate_strategy == 'D1':
            return get_product_linear_fair(children, bound)

        elif self._propagate_strategy == 'linear_bias':
            return get_product_linear_bias(children, bound)

        else:
            self._log('Unknown propagate strategy {}'.format(
                self._propagate_strategy)
            )
            return []


class BodyFuzzer_Drop(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print, strategy='single'):
        BodySchemaStructuralFuzzer.__init__(self, LOG, strategy)

    def _kernel_drop(self, fuzzed_items):
        if not fuzzed_items:
            # not generating redundant tests (no child)
            return [[]]

        if self._is_single_mode():
            fuzzed_pool = [
                [[m[0]] for m in fuzzed_items[:idx] + fuzzed_items[idx + 1:]]
                for idx, _ in enumerate(fuzzed_items)
            ]
        else:
            fuzzed_pool = [
                fuzzed_items[:idx] + fuzzed_items[idx + 1:]
                for idx, _ in enumerate(fuzzed_items)
            ]
        return [fuzzed_items] + fuzzed_pool

    def _fuzz_members_in_object(self, fuzzed_members):
        return self._kernel_drop(fuzzed_members)

    def _fuzz_values_in_array(self, fuzzed_values):
        return self._kernel_drop(fuzzed_values)


class BodyFuzzer_Select(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print, strategy='single'):
        BodySchemaStructuralFuzzer.__init__(self, LOG, strategy)

    def _kernel_select(self, fuzzed_items):
        if len(fuzzed_items) == 1:
            # not generating redundant tests (single child)
            return [fuzzed_items]

        if self._is_single_mode():
            fuzzed_pool = [
                [[items[0]]] for items in fuzzed_items
            ]
        else:
            fuzzed_pool = [
                [items] for items in fuzzed_items
            ]
        return [fuzzed_items] + fuzzed_pool

    def _fuzz_members_in_object(self, fuzzed_members):
        return self._kernel_select(fuzzed_members)

    def _fuzz_values_in_array(self, fuzzed_values):
        return self._kernel_select(fuzzed_values)


class BodyFuzzer_Duplicate(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print, strategy='single'):
        BodySchemaStructuralFuzzer.__init__(self, LOG, strategy)

    def _kernel_duplicate(self, fuzzed_items):
        if not fuzzed_items:
            # not generating redundant tests
            return [[]]

        if self._is_single_mode():
            fuzzed_pool = [
                [[m[0]] for m in [items] + fuzzed_items] for items in fuzzed_items
            ]
        else:
            fuzzed_pool = [
                [items] + fuzzed_items for items in fuzzed_items
            ]
        return [fuzzed_items] + fuzzed_pool

    def _fuzz_members_in_object(self, fuzzed_members):
        return self._kernel_duplicate(fuzzed_members)

    def _fuzz_values_in_array(self, fuzzed_values):
        return self._kernel_duplicate(fuzzed_values)


class BodyFuzzer_Duplicate_Object(BodyFuzzer_Duplicate):
    def __init__(self, LOG=print):
        BodyFuzzer_Duplicate.__init__(self, LOG)

    def _fuzz_values_in_array(self, fuzzed_values):
        return [fuzzed_values]


class BodyFuzzer_Duplicate_Array(BodyFuzzer_Duplicate):
    def __init__(self, LOG=print):
        BodyFuzzer_Duplicate.__init__(self, LOG)

    def _fuzz_members_in_object(self, fuzzed_members):
        return [fuzzed_members]


class BodyFuzzer_Type(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print, strategy='single'):
        BodySchemaStructuralFuzzer.__init__(self, LOG, strategy)

    #
    # Internal nodes
    #
    def _fuzz_object(self, param_object, fuzzed_members):
        pool = BodySchemaStructuralFuzzer._fuzz_object(
            self, param_object, fuzzed_members)

        return pool + [
            ParamBoolean(),    # no __item__
            ParamNumber(),     # no __item__
            ParamString(),     # enumerable
            ParamArray([]),    # enumerable
            ParamObjectLeaf()  # same type (but leaf)
        ]

    def _fuzz_array(self, param_array, fuzzed_values):
        pool = BodySchemaStructuralFuzzer._fuzz_array(
            self, param_array, fuzzed_values)

        return pool + [
            ParamBoolean(),    # no __item__
            ParamNumber(),     # no __item__
            ParamString(),     # enumerable
            ParamObjectLeaf()  # enumerable
        ]

    #
    # Leaf nodes
    #
    def _fuzz_string(self, param_string):
        return [
            param_string,
            ParamObjectLeaf(),  # non-standard value
            ParamArray([]),     # non-standard value
            ParamBoolean(),     # no arithmetic op
            ParamNumber()
        ]

    def _fuzz_number(self, param_number):
        return [
            param_number,
            ParamObjectLeaf(),  # non-standard value
            ParamArray([]),     # non-standard value
            ParamBoolean(),     # no arithmetic op
            ParamString()
        ]

    def _fuzz_boolean(self, param_boolean):
        return [
            param_boolean,
            ParamObjectLeaf(),  # non-standard value
            ParamArray([]),     # non-standard value
            ParamString(),
            ParamNumber()
        ]

    def _fuzz_object_leaf(self, param_object):
        return [
            param_object,
            ParamBoolean(),  # no __item__
            ParamNumber(),   # no __item__
            ParamString(),   # enumerable
            ParamArray([])   # enumerable
        ]


class BodyFuzzer_Type_Cheap(BodyFuzzer_Type):
    def __init__(self, LOG=print):
        BodyFuzzer_Type.__init__(self, LOG)

    def _fuzz_object(self, param_object, fuzzed_members):
        return BodyFuzzer_Type._fuzz_object(
            self, param_object, fuzzed_members)[:-4]

    def _fuzz_array(self, param_array, fuzzed_values):
        return BodyFuzzer_Type._fuzz_array(
            self, param_array, fuzzed_values)[:-3]

    def _fuzz_string(self, param_string):
        return BodyFuzzer_Type._fuzz_string(self, param_string)[:2]

    def _fuzz_number(self, param_number):
        return BodyFuzzer_Type._fuzz_number(self, param_number)[:2]

    def _fuzz_boolean(self, param_boolean):
        return BodyFuzzer_Type._fuzz_boolean(self, param_boolean)[:2]

    def _fuzz_object_leaf(self, param_object):
        return BodyFuzzer_Type._fuzz_object_leaf(self, param_object)[:2]


class BodyFuzzer_DropMember(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print):
        BodySchemaStructuralFuzzer.__init__(self, LOG)

    def _fuzz_members_in_object(self, fuzzed_members):
        # include the seed
        pool = [fuzzed_members]
        for idx, _ in enumerate(fuzzed_members):
            pool.append(
                fuzzed_members[:idx] + fuzzed_members[idx + 1:]
            )
        return pool


class BodyFuzzer_DropOnlyOneMember(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print):
        BodySchemaStructuralFuzzer.__init__(self, LOG, 'single')

    def _fuzz_members_in_object(self, fuzzed_members):
        # the first one should be the original one
        pool = [fuzzed_members]
        for idx, _ in enumerate(fuzzed_members):
            # only keep the first variant (original structure)
            new_member = [[m[0]]
                          for m in fuzzed_members[:idx] + fuzzed_members[idx + 1:]]
            pool.append(new_member)
        return pool


class BodyFuzzer_SelectMember(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print):
        BodySchemaStructuralFuzzer.__init__(self, LOG)

    def _fuzz_members_in_object(self, fuzzed_members):
        # include the seed
        pool = [fuzzed_members]
        for _, members in enumerate(fuzzed_members):
            pool.append([members])
        return pool


class BodyFuzzer_SelectOnlyOneMember_Tree(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print):
        BodySchemaStructuralFuzzer.__init__(self, LOG, 'single')

    def _fuzz_members_in_object(self, fuzzed_members):
        # the first one should be the original one
        pool = [fuzzed_members]
        for _, members in enumerate(fuzzed_members):
            # only keep the first variant (original structure)
            pool.append([[members[0]]])
        return pool


class BodyFuzzer_SelectOnlyOneMember_Path(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print):
        BodySchemaStructuralFuzzer.__init__(self, LOG, 'single')

    def _fuzz_members_in_object(self, fuzzed_members):
        # the first one should be ONLY the original structure
        pool = [[[m[0]] for m in fuzzed_members]]
        for _, members in enumerate(fuzzed_members):
            pool.append([members])
        return pool


class BodyFuzzer_Select2Member(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print):
        BodySchemaStructuralFuzzer.__init__(self, LOG)

    def _fuzz_members_in_object(self, fuzzed_members):
        pool = []
        combination = itertools.combinations(fuzzed_members, 2)
        for c in combination:
            pool.append(c)

        return pool


class BodyFuzzer_Array(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print):
        BodySchemaStructuralFuzzer.__init__(self, LOG)

    def _fuzz_values_in_array(self, fuzzed_values):
        # initialize with an empty array
        pool = [[]]

        if fuzzed_values:
            # single
            pool.append(fuzzed_values[:1])
            # double
            pool.append(fuzzed_values + fuzzed_values)
            # others, e.g., larger?
            # XXX for larger array, we may want to set it to constant
        else:
            # TODO insert dummy nodes
            pass

        return pool


class BodyFuzzer_TypeLeaf(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print, strategy='single'):
        BodySchemaStructuralFuzzer.__init__(self, LOG, strategy)

    def _fuzz_string(self, param_string):
        return [
            param_string,
            ParamObjectLeaf(),  # non-standard value
            ParamArray([]),     # non-standard value
            ParamBoolean(),     # no arithmetic op
            ParamNumber()
        ]

    def _fuzz_number(self, param_number):
        return [
            param_number,
            ParamObjectLeaf(),  # non-standard value
            ParamArray([]),     # non-standard value
            ParamBoolean(),     # no arithmetic op
            ParamString()
        ]

    def _fuzz_boolean(self, param_boolean):
        return [
            param_boolean,
            ParamObjectLeaf(),  # non-standard value
            ParamArray([]),     # non-standard value
            ParamString(),
            ParamNumber()
        ]

    def _fuzz_object_leaf(self, param_object):
        return [
            param_object,
            ParamBoolean(),  # no __item__
            ParamNumber(),   # no __item__
            ParamString(),   # enumerable
            ParamArray([])   # enumerable
        ]


class BodyFuzzer_TypeInternal(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print, strategy='single'):
        BodySchemaStructuralFuzzer.__init__(self, LOG, strategy)

    def _fuzz_object(self, param_object, fuzzed_members):
        pool = BodySchemaStructuralFuzzer._fuzz_object(
            self, param_object, fuzzed_members)

        return pool + [
            ParamBoolean(),    # no __item__
            ParamNumber(),     # no __item__
            ParamString(),     # enumerable
            ParamArray([]),    # enumerable
            ParamObjectLeaf()  # same type (but leaf)
        ]

    def _fuzz_array(self, param_array, fuzzed_values):
        pool = BodySchemaStructuralFuzzer._fuzz_array(
            self, param_array, fuzzed_values)

        return pool + [
            ParamBoolean(),    # no __item__
            ParamNumber(),     # no __item__
            ParamString(),     # enumerable
            ParamObjectLeaf()  # enumerable
        ]


class BodyFuzzer_DuplicateMember(BodySchemaStructuralFuzzer):
    def __init__(self, LOG=print, strategy='single'):
        BodySchemaStructuralFuzzer.__init__(self, LOG, strategy)

    def _fuzz_members_in_object(self, fuzzed_members):
        pool = [fuzzed_members]
        for _, members in enumerate(fuzzed_members):
            new_member = [members] + fuzzed_members
            if self._is_single_mode():
                pool.append(
                    [[m[0]] for m in new_member]
                )
            else:
                pool.append(new_member)

        return pool


if __name__ == '__main__':
    # Unit testing the schema fuzzer
    parser = argparse.ArgumentParser()
    parser.add_argument('grammar', help='Compiler generated grammar file')
    args = parser.parse_args()

    # selected tested
    schema_fuzzer_list = [
        BodyFuzzer_Drop(print, 'single'),
        BodyFuzzer_Drop(print, 'path'),
        BodyFuzzer_Drop(print, 'all'),
        BodyFuzzer_Select(print, 'single'),
        BodyFuzzer_Select(print, 'path'),
        BodyFuzzer_Select(print, 'all'),
        BodyFuzzer_Duplicate(print, 'single'),
        BodyFuzzer_Duplicate(print, 'path'),
        BodyFuzzer_Duplicate(print, 'all'),
        BodyFuzzer_Type(print, 'single'),
        BodyFuzzer_Type(print, 'path'),
        BodyFuzzer_Type(print, 'all'),
        BodyFuzzer_Duplicate_Object(),
        BodyFuzzer_Duplicate_Array(),
        BodyFuzzer_Type_Cheap(),
        BodyFuzzer_DropMember(),
        BodyFuzzer_DropOnlyOneMember(),
        BodyFuzzer_SelectMember(),
        BodyFuzzer_SelectOnlyOneMember_Path(),
        BodyFuzzer_SelectOnlyOneMember_Tree(),
        BodyFuzzer_TypeLeaf(print, 'single'),
        BodyFuzzer_TypeLeaf(print, 'path'),
        BodyFuzzer_TypeLeaf(print, 'all'),
        BodyFuzzer_TypeInternal(print, 'single'),
        BodyFuzzer_TypeInternal(print, 'path'),
        BodyFuzzer_TypeInternal(print, 'all')
    ]

    with open(args.grammar, 'r') as fr:
        schema_str = fr.read()
        schema_json = json.loads(schema_str)

    for request_schema_json in schema_json['Requests']:
        request_schema = RequestSchema(request_schema_json)

        if request_schema.body:
            for schema_fuzzer in schema_fuzzer_list:
                sub_schemas = schema_fuzzer.run(request_schema.body)
                assert(len(sub_schemas) != 0)
                del sub_schemas
