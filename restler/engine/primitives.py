# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""  Primitive types supported by restler. """
from __future__ import print_function
import sys
import time
import datetime
import uuid

from restler_settings import Settings

class CandidateValueException(Exception):
    pass

class UnsupportedPrimitiveException(Exception):
    """ Raised if unknown primitive found in mutations dictionary """
    pass

class InvalidDictPrimitiveException(Exception):
    """ Raised if dict primitive is not a dict type in the mutations dictionary.
    e.g. a restler_custom_payload is received as a list
    """
    pass

# Year-Month-Date format used by restler_fuzzable_datetime
PAYLOAD_DATE_FORMAT = '%Y-%m-%d'

# primitive types
STATIC_STRING = "restler_static_string"
FUZZABLE_STRING = "restler_fuzzable_string"
FUZZABLE_DELIM = "restler_fuzzable_delim"
FUZZABLE_UUID4 = "restler_fuzzable_uuid4"
FUZZABLE_GROUP = "restler_fuzzable_group"
FUZZABLE_BOOL = "restler_fuzzable_bool"
FUZZABLE_INT = "restler_fuzzable_int"
FUZZABLE_NUMBER = "restler_fuzzable_number"
FUZZABLE_DATETIME = "restler_fuzzable_datetime"
FUZZABLE_OBJECT = "restler_fuzzable_object"
FUZZABLE_MULTIPART_FORMDATA = "restler_multipart_formdata"
CUSTOM_PAYLOAD = "restler_custom_payload"
CUSTOM_PAYLOAD_HEADER = "restler_custom_payload_header"
CUSTOM_PAYLOAD_UUID4_SUFFIX = "restler_custom_payload_uuid4_suffix"
REFRESHABLE_AUTHENTICATION_TOKEN = "restler_refreshable_authentication_token"
SHADOW_VALUES = "shadow_values"

# Optional argument passed to grammar function definition functions
QUOTED_ARG = 'quoted'
# Suffix present in always-unquoted primitive lists in the mutations dictionary.
UNQUOTED_STR = '_unquoted'

class CandidateValues(object):
    def __init__(self):
        self.unquoted_values = []
        self.values = []

    def get_flattened_and_quoted_values(self, quoted):
        """ Quotes values as needed and then merges the quoted and unquoted values
        into a single list to be returned.

        @param quoted: If true, quote the quotable values
        @type  quoted: Bool
        @return: The flattened list of candidate values
        @rtype : List[str]

        """
        # First check to see if the values are only a single value, e.g. for uuid4_suffix values
        if self.values and not isinstance(self.values, list):
            return f'"{self.values}"' if quoted else self.values
        elif self.unquoted_values and not isinstance(self.unquoted_values, list):
            return self.unquoted_values

        final_values = []
        if quoted:
            # Quote each value
            for val in self.values:
                final_values.append(f'"{val}"')
        else:
            if self.values:
                final_values.extend(self.values)
        if self.unquoted_values:
            final_values.extend(self.unquoted_values)
        return final_values

class CandidateValuesPool(object):

    def __init__(self):
        """ Initializes all request primitive types supported by restler.

        @return: None
        @rtype : None

        """
        self.candidate_values = {}

        # Supported primitive types in grammar.
        self.supported_primitive_types = [
            STATIC_STRING,
            FUZZABLE_STRING,
            FUZZABLE_DELIM,
            FUZZABLE_UUID4,
            FUZZABLE_GROUP,
            FUZZABLE_BOOL,
            FUZZABLE_INT,
            FUZZABLE_NUMBER,
            FUZZABLE_DATETIME,
            FUZZABLE_OBJECT,
            FUZZABLE_MULTIPART_FORMDATA,
            CUSTOM_PAYLOAD,
            CUSTOM_PAYLOAD_HEADER,
            CUSTOM_PAYLOAD_UUID4_SUFFIX,
            REFRESHABLE_AUTHENTICATION_TOKEN,
            SHADOW_VALUES
        ]
        self.supported_primitive_dict_types = [
            CUSTOM_PAYLOAD,
            CUSTOM_PAYLOAD_HEADER,
            CUSTOM_PAYLOAD_UUID4_SUFFIX,
            REFRESHABLE_AUTHENTICATION_TOKEN,
            SHADOW_VALUES
        ]
        for primitive in self.supported_primitive_types:
            self.candidate_values[primitive] = CandidateValues()
        for primitive in self.supported_primitive_dict_types:
            self.candidate_values[primitive] = dict()

        self.per_endpoint_candidate_values = {}

        self._create_fuzzable_dates()
        self._dates_added = False

    def _create_fuzzable_dates(self):
        """ Creates dates for future and past, which can be added to a list
        of restler_fuzzable_datetime candidate values

        @return: None
        @rtype : None

        """
        today = datetime.datetime.today()
        # Make sure we add enough days to account for a long fuzzing run
        days_to_add = datetime.timedelta(days = (Settings().time_budget / 24) + 1)
        future = today + days_to_add
        self._future_date = future.strftime(PAYLOAD_DATE_FORMAT)
        oneday = datetime.timedelta(days=1)
        yesterday = today - oneday
        self._past_date = yesterday.strftime(PAYLOAD_DATE_FORMAT)

    def _add_fuzzable_dates(self, candidate_values):
        """ Adds fuzzable dates to a candidate values dict

        @param candidate_values: The candidate values to add the dates to
        @type  candidate_values: Dict

        @return: None
        @rtype : None

        """
        if FUZZABLE_DATETIME in candidate_values:
            candidate_values[FUZZABLE_DATETIME].values.append(self._future_date)
            candidate_values[FUZZABLE_DATETIME].values.append(self._past_date)

    def _set_custom_values(self, current_primitives, custom_mutations):
        """ Helper that sets the custom primitive values

        @param current_primitives: The current primitive values that will be updated
                              with the custom values
        @type  current_primitives: Dict
        @param custom_mutations: The custom mutations that will be used to update,
                               i.e. from the mutations dictionary
        @type  custom_mutations: Dict

        @return: The current primitive values updated with the new custom values
        @rtype : Dict

        """
        def _assign_values(candidate_values, custom_values):
            """ Assigns custom mutations values to the candidate values list """
            if UNQUOTED_STR in primitive:
                candidate_values.unquoted_values = custom_values
            else:
                candidate_values.values = custom_values
            return candidate_values

        for primitive in custom_mutations:
            # Create variable for the matching non-unquoted primitive that's used in the grammmar
            #   Example:
            #     dictionary: restler_fuzzable_string_unquoted
            #     grammar   : restler_fuzzable_string
            grammar_primitive = primitive.replace(UNQUOTED_STR, '')

            if grammar_primitive not in self.supported_primitive_types:
                raise UnsupportedPrimitiveException(primitive)

            # For custom primitive types, a dict is needed to define the name of the type,
            # so each value in the dict contains its own list of candidate values, thus they
            # must be handled differently than built-in primitive types.
            if grammar_primitive in self.supported_primitive_dict_types:
                if not isinstance(custom_mutations[primitive], dict):
                    raise InvalidDictPrimitiveException(f'primitive: {primitive}, type: {type(custom_mutations[primitive])}')
                # tag is the key in dict types.
                #   Example:
                #     restler_custom_payload {
                #         "tag1": ["val1", "val2"],
                #         "tag2": ["val3"]
                #     }
                for tag in custom_mutations[primitive]:
                    if tag not in current_primitives[grammar_primitive]:
                        current_primitives[grammar_primitive][tag] = CandidateValues()
                    current_primitives[grammar_primitive][tag] =\
                        _assign_values(current_primitives[grammar_primitive][tag], custom_mutations[primitive][tag])
            else:
                current_primitives[grammar_primitive] = _assign_values(current_primitives[grammar_primitive], custom_mutations[primitive])

        return current_primitives

    def get_candidate_values(self, primitive_name, request_id=None, tag=None, quoted=False):
        """ Return feasible values for a given primitive.

        @param primitive_name: The primitive whose feasible values we wish to fetch.
        @type primitive_name: Str
        @param request_id: The request ID of the request to get values for
        @type  request_id: Int
        @param tag: The tag (key) when getting for dict types
        @type  tag: Str
        @param quoted: If True, quote the strings in the quoted list before returning
        @type  quoted: Bool

        @return: Feasible values for a given primitive.
        @rtype : List or dict

        """
        def _flatten_and_quote_candidate_values(candidate_vals):
            """ Returns a merged list of quoted and unquoted candidate values """
            # First check for dict type. This can occur if get_candidate_values
            # was called on a dict type without a specific tag/key.
            if isinstance(candidate_vals, dict):
                retval = dict()
                for key in candidate_vals:
                    retval[key] = candidate_vals[key].get_flattened_and_quoted_values(quoted)
            else:
                retval = candidate_vals.get_flattened_and_quoted_values(quoted)
            return retval

        candidate_values = self.candidate_values
        if request_id and request_id in self.per_endpoint_candidate_values:
            candidate_values = self.per_endpoint_candidate_values[request_id]

        if primitive_name not in candidate_values:
            print ("\n\n\n\t *** Can't get unsupported primitive: {}\n\n\n".\
                   format(primitive_name))
            raise CandidateValueException

        try:
            if tag:
                if tag in candidate_values[primitive_name]:
                   return _flatten_and_quote_candidate_values(candidate_values[primitive_name][tag])
                # tag not specified in per_endpoint values, try sending from default list
                return _flatten_and_quote_candidate_values(self.candidate_values[primitive_name][tag])
            else:
                if primitive_name in candidate_values:
                    return _flatten_and_quote_candidate_values(candidate_values[primitive_name])
                # primitive value not specified in per_endpoint values, try sending from default list
                return _flatten_and_quote_candidate_values(self.candidate_values[primitive_name])
        except KeyError:
            raise CandidateValueException

    def get_fuzzable_values(self, primitive_type, default_value, request_id=None, quoted=False):
        """ Return list of fuzzable values with a default value (specified)
        in the front of the list.

        Note: If default value is already in the list pulled from candidate values
        it will move that value to the front of the list

        @param primitive_type: The type of the primitive to get the fuzzable values for
        @type  primitive_type: Str
        @param default_value: The default value to use if no fuzzable values exist
        @type  default_value: Str
        @param request_id: The request ID of the request to get values for
        @type  request_id: Int
        @param quoted: If True, quote the strings in the quoted list before returning
        @type  quoted: Bool

        @return: List of fuzzable values
        @rtype : List[str]

        """
        fuzzable_values = list(
            self.get_candidate_values(primitive_type, request_id, quoted=quoted)
        )

        if quoted:
            default_value = f'"{default_value}"'
        # Only use the default value if no values are defined in
        # the dictionary for that fuzzable type
        if not fuzzable_values:
            fuzzable_values.append(default_value)
        elif primitive_type == FUZZABLE_DATETIME and\
        len(fuzzable_values) == 2:
            # Special case for fuzzable_datetime because there will always be
            # two additional values for past/future in the list
            fuzzable_values.insert(0, default_value)

        return fuzzable_values

    def set_candidate_values(self, custom_values, per_endpoint_custom_mutations=None):
        """ Overrides default primitive type values with user-provided ones.

        @param custom_values: Dictionary of user-provided primitive type values.
        @type custom_values: Dict
        @param per_endpoint_custom_mutations: The per-endpoint custom mutations
        @type  per_endpoint_custom_mutations: Dict

        @return: None
        @rtype : None

        """
        # Set default primitives
        self.candidate_values = self._set_custom_values(self.candidate_values, custom_values)
        if not self._dates_added:
            self._add_fuzzable_dates(self.candidate_values)
            self._dates_added = True
        # Set per-resource primitives
        if per_endpoint_custom_mutations:
            for request_id in per_endpoint_custom_mutations:
                self.per_endpoint_candidate_values[request_id] = {}
                for primitive in self.supported_primitive_types:
                    if primitive in self.supported_primitive_dict_types:
                        self.per_endpoint_candidate_values[request_id][primitive] = dict()
                    else:
                        self.per_endpoint_candidate_values[request_id][primitive] = CandidateValues()
                self.per_endpoint_candidate_values[request_id] =\
                    self._set_custom_values(
                        self.per_endpoint_candidate_values[request_id],
                        per_endpoint_custom_mutations[request_id]
                    )
                self._add_fuzzable_dates(self.per_endpoint_candidate_values[request_id])

def restler_static_string(*args, **kwargs):
    """ Static string primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a static
                    string primitive and therefore the arguments will be the one
                    and only mutation from the current primitive.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_fuzzable_string(*args, **kwargs):
    """ Fuzzable string primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a fuzzable
                    string and therefore the argument will be added to the
                    existing candidate values for string mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted

def restler_fuzzable_int(*args, **kwargs):
    """ Integer primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a fuzzable
                    int and therefore the argument will be added to the
                    existing candidate values for int mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_fuzzable_bool(*args, **kwargs):
    """ Boolean primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a fuzzable
                    bool and therefore the argument will be added to the
                    existing candidate values for bool mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_fuzzable_number(*args, **kwargs):
    """ Number primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a fuzzable
                    number and therefore the argument will be added to the
                    existing candidate values for number mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_fuzzable_delim(*args, **kwargs):
    """ Delimiter primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a fuzzable
                    delim and therefore the argument will be added to the
                    existing candidate values for delim mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_fuzzable_group(*args, **kwargs):
    """ Enum primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a group
                    primitive, i.e., an enum -- which is a special case and the
                    first argument is its tag while the second argument should
                    be a list of the enum values.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    try:
        enum_vals = args[1]
    except IndexError:
        enum_vals = [""]
    enum_vals = list(map(lambda x: '{}'.format(x), enum_vals))

    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, enum_vals, quoted


def restler_fuzzable_uuid4(*args, **kwargs):
    """ uuid primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a uuid4
                    primitive and therefore the arguments will be just a tag
                    for the respective uuid4 field.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_fuzzable_datetime(*args, **kwargs) :
    """ datetime primitive

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a date-time
                    primitive and therefore the arguments will be added to the
                    existing candidate values for date-time mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """

    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted

def restler_fuzzable_object(*args, **kwargs) :
    """ object primitive ({})

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a date-time
                    primitive and therefore the arguments will be added to the
                    existing candidate values for object mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple
    """

    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted

def restler_multipart_formdata(*args, **kwargs):
    """ Multipart/formdata primitive

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a multipart
                    form data primitive which will be rendered in requests
                    according to the mime type handling defined under mime
                    module and the user-provided values as custom mutations.
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_custom_payload(*args, **kwargs):
    """ Custom payload primitive.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a custom
                    payload which means that the user should have provided its
                    exact value (to be rendered with).
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_custom_payload_header(*args, **kwargs):
    """ Custom payload primitive for header.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a custom
                    payload which means that the user should have provided its
                    exact value (to be rendered with).
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_custom_payload_uuid4_suffix(*args, **kwargs):
    """ Custom payload primitive with uuid suffix.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a custom
                    payload which means that the user should have provided its
                    exact value (to be rendered with).
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted


def restler_refreshable_authentication_token(*args, **kwargs):
    """ Custom refreshable authentication token.

    @param args: The argument with which the primitive is defined in the block
                    of the request to which it belongs to. This is a custom
                    payload which means that the user should have provided its
                    exact value (to be rendered with).
    @type  args: Tuple
    @param kwargs: Optional keyword arguments.
    @type  kwargs: Dict

    @return: A tuple of the primitive's name and its default value or its tag
                both passed as arguments via the restler grammar.
    @rtype : Tuple

    """
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted
