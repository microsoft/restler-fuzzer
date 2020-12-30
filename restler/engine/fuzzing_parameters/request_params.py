# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
import json

import engine.primitives as primitives
from engine.fuzzing_parameters.fuzzing_config import *

TAG_SEPARATOR = '/'
FUZZABLE_GROUP_TAG = "fuzzable_group_tag"

class QueryParam():
    """ Query Parameter Class
    """
    def __init__(self, key, content):
        """ Initializes a Query Parameter
        """
        self._key = key
        self._content = content

    @property
    def key(self):
        return self._key

    @property
    def content(self):
        return self._content

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

    def get_blocks(self):
        """ Gets the request blocks for the Query Parameter.

        @return: Request blocks representing the format: key=ParamObject
        @rtype : List[str]

        """
        key = primitives.restler_static_string(f'{self._key}=')
        return [key] + self._content.get_blocks(FuzzingConfig())

class QueryList():
    """ List of QueryParam objects
    """
    def __init__(self):
        """ Initializes the QueryList
        """
        self._queries = []

    @property
    def queries(self):
        return self._queries

    def __iter__(self):
        yield self._queries

    def __len__(self):
        return len(self._queries)

    def __eq__(self, other):
        """ Operator equals
        """
        if not isinstance(other, QueryList):
            # don't attempt to compare against unrelated types
            return False

        return self._queries == other.queries

    def __hash__(self):
        """ Custom hash function
        """
        _hash = 0
        for query in self._queries:
            _hash += hash(query)
        return _hash

    def append(self, query):
        """ Appends a new query to the end of the Query List

        @param query: The new query to append
        @type  query: QueryParam

        @return: None
        @rtype : None

        """
        self.queries.append(query)

class ParamBase():
    """ Base class for all body parameters """
    def __init__(self):
        self._fuzzable = False
        self._tag = ''

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

    def meta_copy(self, src):
        """ Copy meta data of a ParamValue

        @param src: Source parameter
        @type  src: ParamValue

        @return: None
        @rtype:  None

        """
        self.set_fuzzable(src.is_fuzzable())
        self._tag = src._tag

    def set_fuzzable(self, is_fuzzable):
        """ Sets param as fuzzable

        @param is_fuzzable: True if fuzzable
        @type  is_fuzzable: Bool

        @return: None
        @rtype : None

        """
        self._fuzzable = is_fuzzable

    def is_fuzzable(self):
        """ Returns whether or not the param is fuzzable

        @return: True if the param is fuzzable
        @rtype : Bool

        """
        return self._fuzzable

class ParamValue(ParamBase):
    """ Base class for value type parameters. Value can be Object, Array,
    String, Number, Boolean, ObjectLeaf, and Enum.
    """
    def __init__(self, custom=False):
        """ Initialize a ParamValue.

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self)
        self._content = None
        self._custom = custom

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
        if self._custom:
            return[primitives.restler_custom_payload(self._content)]
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

    def __init__(self, members):
        """ Initialize an object type parameter

        @param members: A list of members
        @type  members: List [ParamMember]

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self)
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
                fuzzed_members.append(member.get_fuzzing_pool(fuzzer, config))
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
            blocks += member_blocks

            if idx != (len(members_blocks) - 1):
                blocks.append(primitives.restler_static_string(','))

        blocks.append(primitives.restler_static_string('}'))
        return blocks

class ParamArray(ParamBase):
    """ Class for array type parameters """

    def __init__(self, values):
        """ Initialize an array type parameter

        @param values: A list of array values
        @type  values: List [ParamValue]

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self)
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

        for idx, value_blocks in enumerate(values_blocks):
            blocks += value_blocks

            if idx != (len(values_blocks) - 1):
                blocks.append(primitives.restler_static_string(','))

        blocks.append(primitives.restler_static_string(']'))
        return blocks

class ParamString(ParamValue):
    """ Class for string type parameters """

    def __init__(self, custom=False):
        """ Initialize a string type parameter

        @param custom: Whether or not this is a custom payload
        @type  custom: Bool

        @return: None
        @rtype:  None

        """
        ParamValue.__init__(self)
        self._is_custom = custom
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
        if self._is_custom:
            return [primitives.restler_custom_payload(self._content, quoted=True)]
        return [primitives.restler_static_string(self._content, quoted=True)]

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

        if not self.is_fuzzable():
            return [primitives.restler_static_string(default_value, quoted=True)]

        # fuzz as normal fuzzable string
        if not config.merge_fuzzable_values:
            blocks = []
            blocks.append(primitives.restler_fuzzable_string(default_value), quoted=True)
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

    def get_blocks(self, config=None):
        """ Gets request blocks for Uuid Suffix Parameters.

        @return: A request block containing the uuid key
        @rtype : List[str]

        """
        return [primitives.restler_custom_payload_uuid4_suffix(self._content)]

class ParamNumber(ParamValue):
    """ Class for number type parameters """
    @property
    def type(self):
        return int

    def get_signature(self, config):
        """ Returns the Number signature """
        return f'{TAG_SEPARATOR}{self.tag}_num'

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

        if not self.is_fuzzable():
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
    """ Class for Boolean type parameters """
    @property
    def type(self):
        return bool

    def get_signature(self, config):
        """ Returns the boolean signature """
        return f'{TAG_SEPARATOR}{self.tag}_bool'

    def get_fuzzing_blocks(self, config):
        """ Returns the fuzzing request blocks per the config

        @return: The list of request blocks
        @rtype : List[str]

        """
        # default value
        default_value = config.get_default_value(
            self.tag, primitives.FUZZABLE_BOOL
        )
        default_value = str(default_value).lower()

        if not self.is_fuzzable():
            return [primitives.restler_static_string(default_value)]

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
        formalized_content = self._content.replace("'", '"')
        formalized_content = formalized_content.replace('u"', '"')

        return [primitives.restler_static_string(formalized_content)]

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
        default_value = formalize_object_value(default_value)

        # not fuzzalbe --> constant
        if not self.is_fuzzable():
            return [primitives.restler_static_string(default_value)]

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

class ParamEnum(ParamBase):
    """ Class for Enum type parameters """

    def __init__(self, contents, content_type):
        """ Initialize a Enum type parameter

        @param contents: A list of enum contents
        @type  contents: List [str]
        @param content_type: Type of contents
        @type  content_type: Str

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self)
        self._contents = contents
        self._type = content_type

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

    def get_blocks(self, config=None):
        """ Gets request blocks for the Enum Parameters

        @return: Request blocks
        @rtype : List[str]

        """
        contents_str = []

        for content in self._contents:
            content_str = f'"{content}"' if self.content_type == 'String' else content
            contents_str.append(content_str)

        return [primitives.restler_fuzzable_group(FUZZABLE_GROUP_TAG, contents_str)]

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
        contents_str = []

        for content in self._contents:
            # string
            if self._type == 'String':
                content_str = f'"{content}"'
            # others
            else:
                content_str = content

            contents_str.append(content_str)

        return [primitives.restler_fuzzable_group(FUZZABLE_GROUP_TAG, contents_str)]

    def check_type_mismatch(self, check_value):
        # Not relevant for this param type
        pass

    def check_struct_missing(self, check_value, visitor):
        # Not relevant for this param type
        pass

class ParamMember(ParamBase):
    """ Class for member type parameters """

    def __init__(self, name, value):
        """ Initialize a member type parameter

        @param name: Member name
        @type  name: String
        @param value: Member value
        @type  value: ParamValue

        @return: None
        @rtype:  None

        """
        ParamBase.__init__(self)
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

    def get_blocks(self, config=None):
        """ Gets request blocks for the Member Parameters.

        @return: Request blocks representing the format: "key":value
        @rtype : List[str]

        """
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
