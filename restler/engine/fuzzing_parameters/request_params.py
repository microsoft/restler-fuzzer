# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
import json
from abc import ABCMeta, abstractmethod

import engine.primitives as primitives
import engine.dependencies as dependencies
from engine.fuzzing_parameters.fuzzing_config import *

TAG_SEPARATOR = '/'
FUZZABLE_GROUP_TAG = "fuzzable_group_tag"


class ParamProperties:
    """ Properties of request parameters
    """
    def __init__(self, is_required=True, is_readonly=False):
        self._is_readonly = is_readonly
        self._is_required = is_required

    @property
    def is_readonly(self):
        return self._is_readonly

    @property
    def is_required(self):
        return self._is_required


class KeyValueParamBase:
    __metaclass__ = ABCMeta

    """ Abstract base class for parameters that are key-value pairs, such as query
        and header parameters.
    """
    def __init__(self, key, content):
        """ Abstract base constructor for a Key-Value pair Parameter
        """
        self._key = key
        self._content = content

    @property
    def key(self):
        return self._key

    @property
    def content(self):
        return self._content

    @property
    def is_required(self):
        """ Is this a required parameter
        """
        return self.content.is_required

    @property
    def is_readonly(self):
        """ Is this a readonly parameter
        """
        return self.content.is_readonly

    @property
    def is_dynamic_object(self):
        """ Is this a dynamic object
        """
        return self.content.is_dynamic_object

    def type(self):
        return self._type

    def __eq__(self, other):
        """ Operator equals
        """
        if not isinstance(other, QueryParam):
            # don't attempt to compare against unrelated types
            return False
        return self._content == other.content

    def __hash__(self):
        """ Custom hash function
        """
        return hash(self._content)

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The fuzzer object to use for fuzzing
        @type  fuzzer: ParamListSchemaFuzzerBase
        @param config: The configuration for the current fuzzing session
        @type  config: FuzzingConfig

        @return: The fuzzing pool
        @rtype : List[KeyValueParamBase]

        """
        fuzzed_value = self.content.get_fuzzing_pool(fuzzer, config)
        return fuzzer._fuzz_member(self, fuzzed_value)


class QueryParam(KeyValueParamBase):
    """ Query Parameter Class
    """
    def __init__(self, key, content):
        """ Initializes a Query Parameter
        """
        KeyValueParamBase.__init__(self, key, content)

    def get_blocks(self):
        """ Gets the request blocks for the Query Parameter.

        @return: Request blocks representing the format:
                    key=ParamObject
        @rtype : List[str]

        """
        key = primitives.restler_static_string(f'{self._key}=')
        return [key] + self._content.get_blocks(FuzzingConfig())

    def get_original_blocks(self, config=None):
        """ Gets the original request blocks for the Query Parameter.

        @return: Request blocks representing the format:
                    key=ParamObject
        @rtype : List[str]

        """
        include_parameter = config.filter_fn is None or config.filter_fn(self)

        if include_parameter:
            key = primitives.restler_static_string(f'{self._key}=')
            return [key] + self._content.get_original_blocks(config)
        else:
            return []


class HeaderParam(KeyValueParamBase):
    """ Header Parameter Class
    """
    def __init__(self, key, content):
        """ Initializes a Header Parameter
        """
        KeyValueParamBase.__init__(self, key, content)

    def get_blocks(self):
        """ Gets the request blocks for the Header Parameter.

        @return: Request blocks representing the format:
                    key: ParamObject
        @rtype : List[str]

        """
        key = primitives.restler_static_string(f'{self._key}: ')
        return [key] + self._content.get_blocks(FuzzingConfig())

    def get_original_blocks(self, config):
        """ Gets the original request blocks for the Header Parameter.

        @return: Request blocks representing the format:
                    key: ParamObject
        @rtype : List[str]

        """
        include_parameter = config.filter_fn is None or config.filter_fn(self)

        if include_parameter:
            key = primitives.restler_static_string(f'{self._key}: ')
            return [key] + self._content.get_original_blocks(config)
        else:
            return []

class ParamBase:
    """ Base class for all body parameters """
    def __init__(self, param_properties=None, dynamic_object=None, param_name=None, content_type=None, is_quoted=False,
                 custom_payload_type=None):
        self._fuzzable = False
        self._example_values = []
        self._tag = ''
        self._param_properties = param_properties
        self._dynamic_object = dynamic_object
        self._custom_payload_type = custom_payload_type
        self._param_name = param_name
        self._content_type = content_type
        self._is_quoted = is_quoted

    @property
    def tag(self):
        """ Return the param's tag

        @return: The tag
        @rtype : Str

        """
        return self._tag

    @tag.setter
    def tag(self, tag):
        """ Sets the param's tag

        @param tag: The param's tag
        @type  tag: Str

        """
        self._tag = tag

    @property
    def is_required(self):
        """ Returns whether the param is required

        @return: True if the parameter is required
        @rtype:  Bool

        """
        return self._param_properties.is_required

    @property
    def is_readonly(self):
        """ Returns whether the param is readonly

        @return: True if the parameter is readonly
        @rtype:  Bool

        """
        return self._param_properties.is_readonly



    @property
    def example_values(self):
        """ Return the example values

        @return: The example values
        @rtype : list[Str]

        """
        return self._example_values

    @property
    def param_name(self):
        """ Return the param name

        @return: The parameter name
        @rtype : list[Str]

        """
        return self._param_name

    @property
    def is_quoted(self):
        """ Returns whether the param is quoted

        @return: True if the parameter is quoted
        @rtype:  Bool

        """
        return self._is_quoted

    @property
    def dynamic_object_writer_variable(self):
        """ Returns whether the param is a dynamic object writer variable

        @return: True if the parameter is a writer variable
        @rtype:  Bool
        """
        if self._dynamic_object is None:
            return None
        return self._dynamic_object._variable_name

    @property
    def is_dynamic_object_reader(self):
        """ Returns whether the param is a dynamic object reader

        @return: True if the parameter is a dynamic object
        @rtype:  Bool
        """
        return self._dynamic_object is not None and (not self._dynamic_object._is_writer)

    def meta_copy(self, src):
        """ Copy meta data of a ParamValue

        @param src: Source parameter
        @type  src: ParamValue

        @return: None
        @rtype:  None

        """
        self._fuzzable = src._fuzzable
        self._example_values = src._example_values
        self._tag = src._tag
        self._param_properties = src._param_properties
        self._dynamic_object = src._dynamic_object
        self._content_type = src.content_type
        self._is_quoted = src.is_quoted
        self._param_name = src._param_name

    def get_custom_payload(self):
        if self._custom_payload_type is None:
            return None

        if self._custom_payload_type == "String":
            return [primitives.restler_custom_payload(self._content, quoted=self.is_quoted,
                                                      param_name=self.param_name,
                                                      writer=self.dynamic_object_writer_variable)]
        elif self._custom_payload_type == "Header":
            return [primitives.restler_custom_payload_header(self._content, quoted=self.is_quoted,
                                                             param_name=self.param_name,
                                                             writer=self.dynamic_object_writer_variable)]
        elif self._custom_payload_type == "Query":
            return [primitives.restler_custom_payload_query(self._content, quoted=self.is_quoted,
                                                            param_name=self.param_name,
                                                            writer=self.dynamic_object_writer_variable)]
        elif self._custom_payload_type == "UuidSuffix":
            return [primitives.restler_custom_payload_uuid4_suffix(self._content, quoted=self.is_quoted,
                                                                   param_name=self.param_name,
                                                                   writer=self.dynamic_object_writer_variable)]
        else:
            raise Exception(f"Unexpected custom payload type: {self._custom_payload_type}")

    def get_dynamic_object(self):
        if self.is_dynamic_object_reader:
            content = dependencies.RDELIM + self._content + dependencies.RDELIM
            return [primitives.restler_static_string(content, quoted=self.is_quoted)]
        return None

    def get_blocks(self):
        """Returns the blocks for this payload if it defines either a custom payload or dynamic object.
        Otherwise, returns None"""
        custom_payload_blocks = self.get_custom_payload()
        if custom_payload_blocks is not None:
            return custom_payload_blocks

        dynamic_object_blocks = self.get_dynamic_object()
        if dynamic_object_blocks is not None:
            return dynamic_object_blocks
        return None

    def set_fuzzable(self, is_fuzzable):
        """ Sets param as fuzzable

        @param is_fuzzable: True if fuzzable
        @type  is_fuzzable: Bool

        @return: None
        @rtype : None

        """
        self._fuzzable = is_fuzzable

    def set_example_values(self, example_values):
        """ Sets example values for the parameter

        @param example_values: list of entries or None
        @type  example_values: list[String]

        @return: None
        @rtype : None

        """
        self._example_values = example_values

    def set_dynamic_object(self, dynamic_object):
        """ Sets dynamic object

        @param is_fuzzable: True if fuzzable
        @type  is_fuzzable: Bool

        @return: None
        @rtype : None

        """
        self._dynamic_object = dynamic_object

    def set_param_name(self, param_name):
        """ Sets the parameter name for this parameter

        @return: None
        @rtype : None

        """
        self._param_name = param_name


    def set_content_type(self, content_type):
        """ Sets the content type of the parameter

        @return: None
        @rtype : None

        """
        self._content_type = content_type

    @property
    def is_fuzzable(self):
        """ Returns whether or not the param is fuzzable

        @return: True if the param is fuzzable
        @rtype : Bool

        """
        return self._fuzzable

    def content_type(self):
        """ Returns whether or not the param is fuzzable

        @return: True if the param is fuzzable
        @rtype : Bool

        """
        return self._content_type


class ParamValue(ParamBase):
    """ Base class for value type parameters. Value can be Object, Array,
    String, Number, Boolean, ObjectLeaf, and Enum.
    """
    def __init__(self, custom_payload_type=None, param_properties=None, dynamic_object=None, is_quoted=False):
        """ Initialize a ParamValue.

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self, param_properties=param_properties, dynamic_object=dynamic_object, is_quoted=is_quoted,
                           custom_payload_type=custom_payload_type)
        self._content = None

    def __eq__(self, other):
        """ Operator equals
        """
        if not isinstance(other, ParamValue):
            # don't attempt to compare against unrelated types
            return False
        return self._content == other.content

    def __hash__(self):
        """ Custom hash function
        """
        return hash((self._content, self._tag))

    @property
    def content(self):
        """ Return the (payload) content

        @return: Payload content
        @rtype:  None

        """
        return self._content

    @content.setter
    def content(self, content):
        """ Set the (payload) content

        @param content: Payload content
        @type  content: String

        @return: None
        @rtype:  None

        """
        self._content = content

    def count_nodes(self, config):
        """ Returns the number of nodes in this object (0)
        """
        return 0

    def get_signature(self, config):
        """ Returns the value signature (as str) """
        return f'{TAG_SEPARATOR}{self.tag}_str'

    def get_schema_tag_mapping(self, tags: dict, config):
        """ Adds this object's tag to the mapping of tags

        @param tags: The mapping of tags to populate
        @type  tags: Dict(tag: content)

        @return: None
        @rtype : None

        """
        tags.update({self.tag : self._content})

    def get_blocks(self, config=None):
        """ Gets the request blocks for this value param.

        @return: A request block containing the value of the param
        @rtype : List[str]

        """
        base_blocks = ParamBase.get_blocks(self)
        if base_blocks is not None:
            return base_blocks

        return [primitives.restler_static_string(self._content)]

    def get_fuzzing_blocks(self, visitor):
        """ Gets the fuzzing blocks for this param """
        return []

    def check_type_mismatch(self, check_value):
        """ Checks the param for a type mismatch with the check_value string

        @param check_value: The body string that is used to compare with this param
        @type  check_value: Str

        @return: The tag of this param if it found a type mismatch or None
        @rtype : Str or None

        """
        if not isinstance(check_value, self.type):
            return self.tag
        return None

    def check_struct_missing(self, check_value, visitor):
        # Not relevant for this param type
        pass


class ParamObject(ParamBase):
    """ Class for object type parameters """

    def __init__(self, members, param_properties=None):
        """ Initialize an object type parameter

        @param members: A list of members
        @type  members: List [ParamMember]

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self, param_properties=param_properties)
        self._members = members

    def __eq__(self, other):
        """ Operator equals
        """
        if not isinstance(other, ParamObject):
            # don't attempt to compare against unrelated types
            return False

        return self._members == other.members

    def __hash__(self):
        """ Custom hash function
        """
        _hash = 0
        for member in self._members:
            _hash += hash(member)
        return _hash

    @property
    def members(self):
        """ Return the list of members

        @return: The list of members
        @rtype:  List [ParamMember]

        """
        if self._members:
            return self._members
        return []

    def get_schema_tag_mapping(self, tags: dict, config):
        """ Adds this object's tags to the mapping of tags

        @param tags: The mapping of tags to populate
        @type  tags: Dict(tag: content)

        @return: None
        @rtype : None

        """
        if config.depth < config.max_depth:
            config.depth += 1
            for member in self._members:
                member.get_schema_tag_mapping(tags, config)
            config.depth -= 1

    def get_signature(self, config):
        """ Returns the object's signature
        """
        return self._traverse(config, sys._getframe().f_code.co_name, f'{TAG_SEPARATOR}obj')

    def count_nodes(self, config):
        """ Returns the number of nodes in this object
        """
        return self._traverse(config, sys._getframe().f_code.co_name, 1)

    def get_blocks(self, config):
        """ Gets request blocks for the Object Parameters

        @return: Request blocks representing the format: {ParamMember, ParamMember, ...}
        @rtype : List[str]

        """
        members_blocks = self._traverse(config, sys._getframe().f_code.co_name, [])
        return self._get_blocks(members_blocks)

    def get_original_blocks(self, config):
        """ Gets the original request blocks for the Object Parameters

        @return: Request blocks representing the format: {ParamMember, ParamMember, ...}
        @rtype : List[str]

        """
        members_blocks = self._traverse(config, sys._getframe().f_code.co_name, [])
        return self._get_blocks(members_blocks)

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamObject]

        """
        fuzzed_members = []
        if config.depth < config.max_depth:
            config.depth += 1
            for member in self._members:
                member_fuzzing_pool = member.get_fuzzing_pool(fuzzer, config)
                # It is possible that this member was excluded from fuzzing by
                # a filter configured by the fuzzer.  If so, do not add it to
                # 'fuzzed_members'.
                if len(member_fuzzing_pool) > 0:
                    fuzzed_members.append(member_fuzzing_pool)
            config.depth -= 1

        return fuzzer._fuzz_object(self, fuzzed_members)

    def get_fuzzing_blocks(self, config):
        """ Returns blocks used during fuzzing

        @return: The fuzzing pool
        @rtype : List[str]

        """
        members_blocks = self._traverse(config, sys._getframe().f_code.co_name, [])
        return self._get_blocks(members_blocks)

    def check_type_mismatch(self, check_value):
        """ Checks to see if the check_value param is a dict object and then
        checks each object member for its correct type. If any of the param
        types are a mismatch, returns that param's tag.

        @param check_value: The body string that is used to compare with this param
        @type  check_value: Str

        @return: The tag of the mismatched param if a type mismatch was detected or None
        @rtype : Str or None

        """
        if not isinstance(check_value, dict):
            return self.tag

        for member in self._members:
            tag = member.check_type_mismatch(check_value)
            if tag:
                return tag
        return None

    def check_struct_missing(self, check_value, visitor):
        """ Checks each member of this object to see if the struct matches the
        check_value struct. If it does not, the @visitor.val_str will be populated
        with each missing member's tag in the format tag/tag/tag/tag

        @param check_value: The body string that is used to compare with this param
        @type  check_value: Str
        @param visitor: The visitor object that is to be populated during traversal
        @type  visitor: BodySchemaVisitor

        @return: None
        @rtype : None

        """
        for member in self._members:
            visitor.depth += 1
            member.check_struct_missing(check_value, visitor)
            visitor.depth -= 1

    def _traverse(self, config: FuzzingConfig, func: str, accum_value):
        """ Helper function that traverses the object's members

        @param config: The FuzzingConfig for this traversal
        @param func: The function name to call during traversal
        @param accum_value: The value that accumulates during and returns
                            after object traversal

        @return: The accumulated value

        """
        if config.depth < config.max_depth:
            config.depth += 1
            for member in self._members:
                if isinstance(accum_value, list):
                    accum_value.append(getattr(member, func)(config))
                else:
                    accum_value += getattr(member, func)(config)
            config.depth -= 1

        return accum_value

    def _get_blocks(self, members_blocks: list) -> list:
        """ Returns list of request blocks associated with this object

        @param members_blocks: The object's members' blocks retrieved during
                               traversal of this object

        @return: The list of request blocks associated with this object
        @rtype : List[str]

        """
        blocks = []

        blocks.append(primitives.restler_static_string('{'))

        for idx, member_blocks in enumerate(members_blocks):
            # If member_blocks is empty (because the member was filtered), process the next item
            if len(member_blocks) == 0:
                continue

            blocks += member_blocks
            if idx != (len(members_blocks) - 1):
                blocks.append(primitives.restler_static_string(','))

        blocks.append(primitives.restler_static_string('}'))
        return blocks


class ParamArray(ParamBase):
    """ Class for array type parameters """

    def __init__(self, values, param_properties=None):
        """ Initialize an array type parameter

        @param values: A list of array values
        @type  values: List [ParamValue]

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self, param_properties=param_properties)
        self._values = values

    @property
    def values(self):
        """ Return the list of values in the array

        @return: The list of values
        @rtype:  List [ParamValue]

        """
        return self._values

    def get_schema_tag_mapping(self, tags: dict, config):
        """ Adds this object's tags to the mapping of tags

        @param tags: The mapping of tags to populate
        @type  tags: Dict(tag: content)

        @return: None
        @rtype : None

        """
        if config.depth < config.max_depth:
            config.depth += 1
            for value in self._values:
                value.get_schema_tag_mapping(tags, config)
            config.depth -= 1

    def get_signature(self, config):
        """ Returns this array's signature """
        sys._getframe().f_code.co_name
        return self._traverse(config, sys._getframe().f_code.co_name, f'{TAG_SEPARATOR}arr')

    def count_nodes(self, config):
        """ Returns the number of nodes in this object
        """
        return self._traverse(config, sys._getframe().f_code.co_name, 1)

    def get_blocks(self, config):
        """ Gets request blocks for Array Parameters

        @return: Request blocks representing the format: [ParamObject, ParamObject]
        @rtype : List[str]

        """
        values_blocks = self._traverse(config, sys._getframe().f_code.co_name, [])
        return self._get_blocks(values_blocks)

    def get_original_blocks(self, config):
        """ Gets the original request blocks for Array Parameters

        @return: Request blocks representing the format: [ParamObject, ParamObject]
        @rtype : List[str]

        """
        values_blocks = self._traverse(config, sys._getframe().f_code.co_name, [])
        return self._get_blocks(values_blocks)

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamArray]

        """
        fuzzed_values = []

        if config.depth < config.max_depth:
            config.depth += 1
            for value in self._values:
                fuzzed_values.append(value.get_fuzzing_pool(fuzzer, config))
            config.depth -= 1

        return fuzzer._fuzz_array(self, fuzzed_values)

    def get_fuzzing_blocks(self, config):
        """ Gets request blocks for Array Parameters

        @return: Request blocks representing the format: [ParamObject, ParamObject]
        @rtype : List[str]

        """
        values_blocks = self._traverse(config, 'get_fuzzing_blocks', [])
        return self._get_blocks(values_blocks)

    def check_type_mismatch(self, check_value):
        """ Checks to see if the check_value is a list type. If it is not,
        returns this param's tag. If it is a list type, check its first value
        for a type mismatch with check_value's first element.

        @param check_value: The body string that is used to compare with this param
        @type  check_value: Str

        @return: The tag of this param if check_value is not a list, the tag of the
                 first value in this list if it does not match the first element in
                 the check_value list, or None
        @rtype : Str or None

        """
        new_check = check_value
        if not isinstance(check_value, list):
            return self.tag
        elif check_value:
            new_check = check_value[0]

        return self._values[0].check_type_mismatch(new_check)

    def check_struct_missing(self, check_value, visitor):
        """ If this list is empty, add its tag to the @visitor.val_str.
        If not empty, check its first value for a missing struct.

        @param check_value: The body string that is used to compare with this param
        @type  check_value: Str
        @param visitor: The visitor object that is to be populated during traversal
        @type  visitor: BodySchemaVisitor

        @return: None
        @rtype : None

        """
        new_check = check_value
        if check_value is not None:
            if not check_value:
                visitor.val_str += f'{TAG_SEPARATOR}{self.tag}'
                new_check = None
            elif isinstance(check_value, list):
                new_check = check_value[0]

        self._values[0].check_struct_missing(new_check, visitor)

    def _traverse(self, config, func, values_blocks):
        """ Helper function that traverses the array's values

        @param config: The FuzzingConfig for this traversal
        @param func: The function name to call during traversal
        @param accum_value: The value that accumulates during and returns
                            after array traversal

        @return: The accumulated value

        """
        if config.depth < config.max_depth:
            config.depth += 1
            for value in self._values:
                if isinstance(values_blocks, list):
                    values_blocks.append(getattr(value, func)(config))
                else:
                    values_blocks += getattr(value, func)(config)
            config.depth -= 1

        return values_blocks

    def _get_blocks(self, values_blocks):
        """ Returns list of request blocks associated with this array

        @param values_blocks: The array's values' blocks retrieved during
                               traversal of this array

        @return: The list of request blocks associated with this array
        @rtype : List[str]

        """
        blocks = []

        blocks.append(primitives.restler_static_string('['))
        values_blocks_length = len(values_blocks)
        for idx, value_blocks in enumerate(values_blocks):
            if len(value_blocks) == 0:
                continue

            blocks += value_blocks
            if idx != (values_blocks_length - 1):
                blocks.append(primitives.restler_static_string(','))

        blocks.append(primitives.restler_static_string(']'))
        return blocks


class ParamString(ParamValue):
    """ Class for string type parameters """

    def __init__(self, custom_payload_type=None, param_properties=None, dynamic_object=None, is_quoted=True,
                 content_type="String"):
        """ Initialize a string type parameter

        @param custom: Whether or not this is a custom payload
        @type  custom: Bool

        @return: None
        @rtype:  None

        """
        ParamValue.__init__(self, param_properties=param_properties, dynamic_object=dynamic_object, is_quoted=is_quoted,
                            custom_payload_type=custom_payload_type)

        self._content_type = content_type
        self._unknown = False

    @property
    def type(self):
        return (str,bytes)

    @property
    def is_unknown(self):
        return self._unknown

    def set_unknown(self):
        self._unknown = True

    def get_blocks(self, config=None):
        """ Gets request blocks for the String Parameters.

        @return: A request block containing the string
        @rtype : List[str]

        """
        base_blocks = ParamBase.get_blocks(self)
        if base_blocks is not None:
            return base_blocks

        return [primitives.restler_static_string(self._content, quoted=self.is_quoted)]

    def get_original_blocks(self, config=None):
        """ Gets the original request blocks for the String Parameters.

        @return: A request block containing the string
        @rtype : List[str]

        """
        base_blocks = ParamBase.get_blocks(self)
        if base_blocks is not None:
            return base_blocks

        content = self._content

        if self.is_fuzzable:
            if self._content_type == "String":
                return [primitives.restler_fuzzable_string(content, quoted=self.is_quoted, examples=self.example_values,
                                                           param_name=self.param_name,
                                                           writer=self.dynamic_object_writer_variable)]
            elif self._content_type == "Uuid":
                return [primitives.restler_fuzzable_uuid4(content, quoted=self.is_quoted, examples=self.example_values,
                                                          param_name=self.param_name,
                                                          writer=self.dynamic_object_writer_variable)]
            elif self._content_type == "DateTime":
                return [primitives.restler_fuzzable_datetime(content, quoted=self.is_quoted,
                                                             examples=self.example_values,
                                                             param_name=self.param_name,
                                                             writer=self.dynamic_object_writer_variable)]
            elif self._content_type == "Date":
                return [primitives.restler_fuzzable_date(content, quoted=self.is_quoted, examples=self.example_values,
                                                         param_name=self.param_name,
                                                         writer=self.dynamic_object_writer_variable)]
            else:
                raise Exception(f"Unexpected content type: {self._content_type}")

        return [primitives.restler_static_string(content, quoted=self.is_quoted)]

    def get_fuzzing_blocks(self, config):
        """ Returns the fuzzing request blocks per the config

        @return: The list of request blocks
        @rtype : List[str]

        """
        # default value
        default_value = config.get_default_value(
            self.tag, primitives.FUZZABLE_STRING, self._content
        )

        def not_like_string(val):
            """ Tests if a value seems to be some type other
            than a string (i.e. array, dict, bool, int) """

            if not val or not isinstance(val, str):
                return True

            if val[0] == '[' and val[-1] == ']':
                return True
            if val[0] == '{' and val[-1] == '}':
                return True
            if val.lower() == 'true' or val.lower() == 'false':
                return True

            try:
                v = int(val)
                return True
            except Exception:
                pass

            return False

        if self.is_unknown and not_like_string(default_value):
            # Try to get a new default value without a hint
            default_value = config.get_default_value(
                self.tag, primitives.FUZZABLE_STRING, hint=None
            )
            if not_like_string(default_value):
                return [primitives.restler_static_string(default_value, quoted=False)]

        if not self.is_fuzzable:
            if self.is_dynamic_object_reader:
                content = dependencies.RDELIM + self._content + dependencies.RDELIM
                return [primitives.restler_static_string(content, quoted=self.is_quoted)]
            return [primitives.restler_static_string(default_value, quoted=self.is_quoted)]

        # fuzz as normal fuzzable string
        if not config.merge_fuzzable_values:
            blocks = []
            blocks.append(primitives.restler_fuzzable_string(default_value), quoted=self.is_quoted)
            return blocks

        # get the set of fuzzable values
        fuzzable_values_raw = config.get_fuzzable_values(
            self.tag, primitives.FUZZABLE_STRING
        )

        fuzzable_values = [
            f'"{value}"' for value in fuzzable_values_raw
        ]

        # merge default + fuzzable values
        fuzzable_group = config.cleanup_fuzzable_group(
            f'"{default_value}"', fuzzable_values
        )
        return [primitives.restler_fuzzable_group(FUZZABLE_GROUP_TAG, fuzzable_group)]

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamString]

        """
        return fuzzer._fuzz_string(self)


class ParamUuidSuffix(ParamString):
    """ Class for uuid suffix parameters """

    def get_original_blocks(self, config=None):
        """ Gets the original request blocks for Uuid Suffix Parameters.

        @return: A request block containing the uuid key
        @rtype : List[str]

        """
        return [primitives.restler_custom_payload_uuid4_suffix(self._content,
                                                               quoted=self.is_quoted,
                                                               param_name=self.param_name,
                                                               writer=self.dynamic_object_writer_variable)]

    def get_blocks(self, config=None):
        """ Gets request blocks for Uuid Suffix Parameters.

        @return: A request block containing the uuid key
        @rtype : List[str]

        """
        return self.get_original_blocks(config)


class DynamicObject:
    """ Class for dynamic object variables """
    def __init__(self, primitive_type, variable_name, is_writer):
        self._primitive_type = primitive_type
        self._variable_name = variable_name
        self._is_writer = is_writer

    @property
    def is_writer(self):
        return self._is_writer


class ParamNumber(ParamValue):
    """ Class for number type parameters """
    def __init__(self, param_properties=None, custom_payload_type=None, dynamic_object=None, is_quoted=False, number_type="Int"):
        """ Initialize a number type parameter

        @param custom: Whether or not this is a custom payload
        @type  custom: Bool

        @return: None
        @rtype:  None

        """
        ParamValue.__init__(self, param_properties=param_properties, dynamic_object=dynamic_object, is_quoted=is_quoted,
                            custom_payload_type=custom_payload_type)
        self._number_type = number_type

    @property
    def type(self):
        return int

    def get_signature(self, config):
        """ Returns the Number signature """
        return f'{TAG_SEPARATOR}{self.tag}_num'

    def get_original_blocks(self, config=None):
        """ Gets the original request blocks for the Number Parameters.

        @return: A request block containing the number
        @rtype : List[str]

        """
        base_blocks = ParamBase.get_blocks(self)
        if base_blocks is not None:
            return base_blocks

        content = self._content
        if self._number_type == "Int":
            return [primitives.restler_fuzzable_int(content, quoted=self.is_quoted,
                                                    examples=self.example_values,
                                                    param_name=self.param_name,
                                                    writer=self.dynamic_object_writer_variable)]
        else:
            return [primitives.restler_fuzzable_number(content, quoted=self.is_quoted, examples=self.example_values,
                                                       param_name=self.param_name,
                                                       writer=self.dynamic_object_writer_variable)]


    def get_fuzzing_blocks(self, config):
        """ Returns the fuzzing request blocks per the config

        @return: The list of request blocks
        @rtype : List[str]

        """
        # default value
        default_value = config.get_default_value(
            self.tag, primitives.FUZZABLE_INT
        )
        default_value = str(default_value)

        if not self.is_fuzzable:
            if self.is_dynamic_object_reader:
                default_value = dependencies.RDELIM + default_value + dependencies.RDELIM
            return [primitives.restler_static_string(default_value)]

        # fuzz as normal fuzzable int
        if not config.merge_fuzzable_values:
            return [primitives.restler_fuzzable_int(default_value)]

        # get the set of fuzzable variables
        fuzzable_values_raw = config.get_fuzzable_values(
            self.tag, primitives.FUZZABLE_INT
        )

        fuzzable_values = [
            str(value) for value in fuzzable_values_raw
        ]

        # merge default + fuzzable values
        fuzzable_group = config.cleanup_fuzzable_group(
            default_value, fuzzable_values
        )
        return [primitives.restler_fuzzable_group(FUZZABLE_GROUP_TAG, fuzzable_group)]

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamNumber]

        """
        return fuzzer._fuzz_number(self)

class ParamBoolean(ParamValue):
    def __init__(self, param_properties=None, custom_payload_type=None, dynamic_object=None, is_quoted=False):
        """ Initialize a boolean type parameter
        """
        ParamValue.__init__(self, param_properties=param_properties, dynamic_object=dynamic_object, is_quoted=is_quoted,
                            custom_payload_type=custom_payload_type)

    """ Class for Boolean type parameters """
    @property
    def type(self):
        return bool

    def get_signature(self, config):
        """ Returns the boolean signature """
        return f'{TAG_SEPARATOR}{self.tag}_bool'

    def get_original_blocks(self, config=None):
        """ Gets original request blocks for Boolean Parameters

        @return: Request block
        @rtype : List[str]

        """
        base_blocks = ParamBase.get_blocks(self)
        if base_blocks is not None:
            return base_blocks

        return [primitives.restler_fuzzable_bool(self._content, quoted=self.is_quoted, examples=self.example_values,
                                                 param_name=self.param_name,
                                                 writer=self.dynamic_object_writer_variable)]

    def get_fuzzing_blocks(self, config):
        """ Returns the fuzzing request blocks per the config

        @return: The list of request blocks
        @rtype : List[str]

        """
        # default value
        default_value = config.get_default_value(
            self.tag, primitives.FUZZABLE_BOOL
        )

        if not self.is_fuzzable:
            if self.is_dynamic_object_reader:
                default_value = dependencies.RDELIM + default_value + dependencies.RDELIM
            else:
                default_value = str(default_value).lower()
            return [primitives.restler_static_string(default_value)]

        default_value = str(default_value).lower()
        if not config.merge_fuzzable_values:
            return [primitives.restler_fuzzable_bool(default_value)]

        # get the set of fuzzable variables
        fuzzable_values_raw = config.get_fuzzable_values(
            self.tag, primitives.FUZZABLE_BOOL
        )

        fuzzable_values = [
            str(value) for value in fuzzable_values_raw
        ]

        # merge default + fuzzable values
        fuzzable_group = config.cleanup_fuzzable_group(
            default_value, fuzzable_values
        )
        return [primitives.restler_fuzzable_group(FUZZABLE_GROUP_TAG, fuzzable_group)]

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamBoolean]

        """
        return fuzzer._fuzz_boolean(self)

class ParamObjectLeaf(ParamValue):
    """ Class for leaf object type parameters """
    def __init__(self, param_properties=None, custom_payload_type=None, dynamic_object=None, is_quoted=False):
        """ Initialize an object leaf type parameter
        """
        ParamValue.__init__(self, param_properties=param_properties, dynamic_object=dynamic_object, is_quoted=is_quoted,
                            custom_payload_type=custom_payload_type)


    @property
    def type(self):
        return dict

    def get_signature(self, config):
        """ Returns the ObjectLeaf signature """
        return f'{TAG_SEPARATOR}{self.tag}_obj'

    def get_blocks(self, config=None):
        """ Gets request blocks for Object Leaf Parameters

        @return: Request block
        @rtype : List[str]

        """
        if self.is_dynamic_object_reader:
            content = dependencies.RDELIM + self._content + dependencies.RDELIM
            return [primitives.restler_static_string(content)]

        # If the leaf value is null, return a static string with the value null
        if self._content is None:
            return [primitives.restler_static_string("null")]

        formalized_content = self._content.replace("'", '"')
        formalized_content = formalized_content.replace('u"', '"')

        return [primitives.restler_static_string(formalized_content)]

    def get_original_blocks(self, config=None):
        """ Gets original request blocks for Object Leaf Parameters

        @return: Request block
        @rtype : List[str]

        """
        base_blocks = ParamBase.get_blocks(self)
        if base_blocks is not None:
            return base_blocks

        # This check is present to support older grammars, and can be removed in the future.
        if self._content is None:
            formalized_content = "null"
        else:
            formalized_content = self._content.replace("'", '"')
            formalized_content = formalized_content.replace('u"', '"')

        return [primitives.restler_fuzzable_object(formalized_content, quoted=self.is_quoted,
                                                   examples=self.example_values,
                                                   param_name=self.param_name,
                                                   writer=self.dynamic_object_writer_variable)]

    def get_fuzzing_blocks(self, config):
        """ Returns the fuzzing request blocks per the config

        @return: The list of request blocks
        @rtype : List[str]

        """
        # helper function to sanitize raw object string
        def formalize_object_value(raw_object):
            object_str = str(raw_object)
            object_tmp = object_str.replace("'", '"')
            object_tmp = object_tmp.replace('u"', '"')
            try:
                test_object = json.loads(object_tmp)
                if str(test_object) == raw_object:
                    return object_tmp
            except Exception:
                return '{ "fuzz" : false }'

            return object_str

        # default value
        default_value = config.get_default_value(
            self.tag, primitives.FUZZABLE_OBJECT
        )

        # not fuzzalbe --> constant
        if not self.is_fuzzable:
            if self.is_dynamic_object_reader:
                default_value = dependencies.RDELIM + default_value + dependencies.RDELIM
            else:
                default_value = formalize_object_value(default_value)
            return [primitives.restler_static_string(default_value)]

        default_value = formalize_object_value(default_value)

        # fuzz as normal fuzzable object using wordbook
        if not config.merge_fuzzable_values:
            return [primitives.restler_fuzzable_object(default_value)]

        # get the set of fuzzable values
        fuzzable_values_raw = config.get_fuzzable_values(
            self.tag, primitives.FUZZABLE_OBJECT
        )

        fuzzable_values = [
            formalize_object_value(value) for value in fuzzable_values_raw
        ]

        # merge default + fuzzable values
        fuzzable_group = config.cleanup_fuzzable_group(
            default_value, fuzzable_values
        )
        return [primitives.restler_fuzzable_group(FUZZABLE_GROUP_TAG, fuzzable_group)]

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamObjectLeaf]

        """
        return fuzzer._fuzz_object_leaf(self)


class ParamEnum(ParamValue):
    """ Class for Enum type parameters """
    def __init__(self, contents, content_type,
                 enum_name=FUZZABLE_GROUP_TAG,
                 param_properties=None, custom_payload_type=None, dynamic_object=None, is_quoted=False):
        """ Initialize an Enum type parameter

        @param contents: A list of enum contents
        @type  contents: List [str]
        @param content_type: Type of contents.
        @type  content_type: Str

        @return: None
        @rtype:  None

        """
        ParamValue.__init__(self, param_properties=param_properties, dynamic_object=dynamic_object, is_quoted=is_quoted,
                            custom_payload_type=custom_payload_type)
        self._contents = contents
        self._type = content_type
        self._is_quoted = is_quoted
        self._enum_name = enum_name

    @property
    def contents(self):
        """ Return the list of contents

        @return: The list of enum contents
        @rtype:  List [str]

        """
        return self._contents

    @property
    def content_type(self):
        """ Return the type of contents

        @return: Content type
        @rtype:  String

        """
        return self._type

    def get_signature(self, config):
        """ Returns the enum signature """
        return f'{TAG_SEPARATOR}{self.tag}_enum'

    def get_schema_tag_mapping(self, tags: dict, config):
        # Not relevant for this param type
        pass

    def count_nodes(self, config):
        """ Returns the number of nodes in this object (0)
        """
        return 0

    def _get_fuzzable_group_values(self):
        contents_str = []

        for content in self._contents:
            if self._is_quoted and (self.content_type in ['String', 'Uuid', 'DateTime', 'Date']):
                content_str = f'"{content}"'
            else:
                content_str = content
            contents_str.append(content_str)
        return contents_str

    def get_original_blocks(self, config=None):
        """ Gets the original request blocks for the Enum Parameters

        @return: Request blocks
        @rtype : List[str]

        """
        base_blocks = ParamBase.get_blocks(self)
        if base_blocks is not None:
            return base_blocks

        return [primitives.restler_fuzzable_group(self._enum_name,
                                                  self._contents,
                                                  quoted=self.is_quoted, examples=self.example_values,
                                                  param_name=self.param_name,
                                                  writer=self.dynamic_object_writer_variable)]

    def get_blocks(self, config=None):
        """ Gets request blocks for the Enum Parameters

        @return: Request blocks
        @rtype : List[str]

        """
        return [primitives.restler_fuzzable_group(FUZZABLE_GROUP_TAG,
                                                  self._get_fuzzable_group_values(),
                                                  quoted=self.is_quoted, examples=self.example_values)]

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamEnum]

        """
        return fuzzer._fuzz_enum(self)

    def get_fuzzing_blocks(self, config):
        """ Returns the fuzzing request blocks per the config

        @return: The list of request blocks
        @rtype : List[str]

        """

        # Since Enums are not fuzzed right now, just re-use get_blocks
        return self.get_blocks(config)

    def check_type_mismatch(self, check_value):
        # Not relevant for this param type
        pass

    def check_struct_missing(self, check_value, visitor):
        # Not relevant for this param type
        pass


class ParamMember(ParamBase):
    """ Class for member type parameters """

    def __init__(self, name, value, param_properties=None):
        """ Initialize a member type parameter

        @param name: Member name
        @type  name: String
        @param value: Member value
        @type  value: ParamValue

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self, param_properties=param_properties)
        self._name = name
        self._value = value

    def __eq__(self, other):
        """ Operator equals
        """
        if not isinstance(other, ParamMember):
            # don't attempt to compare against unrelated types
            return False

        return self._name == other.name and self._value == other.value

    def __hash__(self):
        """ Custom hash function
        """
        return hash((self._name, self._value))

    @property
    def name(self):
        """ Return the member name

        @return: Member name
        @rtype:  String

        """
        return self._name

    @property
    def tag(self):
        """ Return the member tag

        @return: Member tag
        @rtype : Str

        """
        # ParamMember tag is its name
        return self._name

    @tag.setter
    def tag(self, tag):
        """ Sets the Member tag

        @param tag: The tag to set
        @type  tag: Str

        """
        # The param's tag is its name
        self._name = tag

    @property
    def value(self):
        """ Return the member value

        @return: Member value
        @rtype:  ParamValue

        """
        return self._value

    def get_signature(self, config):
        """ Returns this member's signature """
        return f'{TAG_SEPARATOR}{self.tag}_mem' + self._value.get_signature(config)

    def get_schema_tag_mapping(self, tags: dict, config):
        """ Adds this object's tags to the mapping of tags

        @param tags: The mapping of tags to populate
        @type  tags: Dict(tag: content)

        @return: None
        @rtype : None

        """
        self._value.get_schema_tag_mapping(tags, config)

    def count_nodes(self, config):
        """ Returns the number of nodes in this object
        """
        return 1 + self._value.count_nodes(config)

    def get_original_blocks(self, config=None):
        """ Gets the original request blocks for the Member Parameters.

        @return: Request blocks representing the format: "key":value
        @rtype : List[str]

        """
        member_blocks = self._value.get_original_blocks(config)

        if config.filter_fn is not None:
            num_included_children = 0
            include_parameter = config.filter_fn(self)
            if isinstance(self._value, ParamObject):
                num_included_children = len(list(filter(config.filter_fn, self._value.members)))

            if not include_parameter and num_included_children == 0:
                return []

        return [primitives.restler_static_string(f'"{self._name}":')] + self._value.get_original_blocks(config)

    def get_blocks(self, config=None):
        """ Gets request blocks for the Member Parameters.

        @return: Request blocks representing the format: "key":value
        @rtype : List[str]

        """
        member_blocks = self._value.get_blocks(config)

        return [primitives.restler_static_string(f'"{self._name}":')] +\
               self._value.get_blocks(config)

    def get_fuzzing_pool(self, fuzzer, config):
        """ Returns the fuzzing pool

        @param fuzzer: The body fuzzer object to use for fuzzing
        @type  fuzzer: BodySchemaStructuralFuzzer

        @return: The fuzzing pool
        @rtype : List[ParamMember]

        """
        fuzzed_value = self._value.get_fuzzing_pool(fuzzer, config)
        return fuzzer._fuzz_member(self, fuzzed_value)

    def get_fuzzing_blocks(self, config):
        """ Returns the fuzzing request blocks of this member

        @return: The list of request blocks
        @rtype : List[str]

        """
        return [primitives.restler_static_string(f'"{self._name}":')] +\
               self._value.get_fuzzing_blocks(config)

    def check_type_mismatch(self, check_value):
        """ If this member exists in the check_value string, check its type to
        see if there is a mismatch

        @param check_value: The body string that is used to compare with this param
        @type  check_value: Str

        @return: The tag of this param's value if it found a type mismatch or None
        @rtype : Str or None

        """
        if check_value is not None and self.name in check_value:
            return self.value.check_type_mismatch(check_value[self.name])

        return None

    def check_struct_missing(self, check_value, visitor):
        """ Checks to see if this member is in check_value. If not, add its name
        to the @visitor.val_str and then continue to check for missing struct within
        its value.

        @param check_value: The body string that is used to compare with this param
        @type  check_value: Str
        @param visitor: The visitor object that is to be populated during traversal
        @type  visitor: BodySchemaVisitor

        @return: None
        @rtype : None

        """
        if check_value is None:
            new_check = None
        elif self.name in check_value:
            new_check = check_value[self.name]
        else:
            depth_str = (visitor.depth - 1) * '+'
            visitor.val_str += f'{TAG_SEPARATOR}{depth_str}{self.name}'
            if isinstance(self.value, ParamObject):
                visitor.val_str += '{...}'
            elif isinstance(self.value, ParamArray):
                visitor.val_str += '[...]'
            return

        self.value.check_struct_missing(new_check, visitor)
