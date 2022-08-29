# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""  Primitive types supported by restler. """
from __future__ import print_function
import sys
import os
import time
import datetime
from datetime import datetime as dt
import uuid
import itertools
import types
from restler_settings import Settings
import utils.import_utilities as import_utilities

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
FUZZABLE_DATE = "restler_fuzzable_date"
FUZZABLE_OBJECT = "restler_fuzzable_object"
FUZZABLE_MULTIPART_FORMDATA = "restler_multipart_formdata"
CUSTOM_PAYLOAD = "restler_custom_payload"
CUSTOM_PAYLOAD_HEADER = "restler_custom_payload_header"
CUSTOM_PAYLOAD_QUERY = "restler_custom_payload_query"
CUSTOM_PAYLOAD_UUID4_SUFFIX = "restler_custom_payload_uuid4_suffix"
REFRESHABLE_AUTHENTICATION_TOKEN = "restler_refreshable_authentication_token"
BASEPATH = "restler_basepath"
SHADOW_VALUES = "shadow_values"

# Optional argument passed to grammar function definition functions
QUOTED_ARG = 'quoted'
# Suffix present in always-unquoted primitive lists in the mutations dictionary.
UNQUOTED_STR = '_unquoted'
# Optional argument passed to fuzzable primitive definition function that can
# provide an example value.  This value is used instead of the default value if present.
EXAMPLES_ARG = 'examples'
# Optional argument passed to fuzzable primitive definition function that can
# provide the name of the parameter being fuzzed.
# This value is used in test-all-combinations mode to allow the user to analyze spec coverage
# for particular parameter values.
PARAM_NAME_ARG = 'param_name'
# Optional argument passed to fuzzable primitive definition function,
# which indicates that the value assigned to the primitive should also be assigned to the
# writer variable (dynamic object) specified.
WRITER_VARIABLE_ARG = 'writer'
# Name of the function that wraps all value generators

def is_date_type(primitive_type):
    return primitive_type in [FUZZABLE_DATE, FUZZABLE_DATETIME]

def is_value_generator(candidate_values):
    """ Returns whether the argument is a value generator
    """
    VALUE_GENERATOR_WRAPPER_FUNC_NAME = "value_generator_wrapper"
    return isinstance(candidate_values, types.FunctionType) and\
            candidate_values.__name__ == VALUE_GENERATOR_WRAPPER_FUNC_NAME

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

    @staticmethod
    def is_custom_fuzzable(primitive_type_name):
        if primitive_type_name in [FUZZABLE_UUID4, FUZZABLE_MULTIPART_FORMDATA, CUSTOM_PAYLOAD_UUID4_SUFFIX]:
            # Dynamic generators for these primitives are currently not supported.
            return False
        return "_fuzzable_" in primitive_type_name or "_custom_" in primitive_type_name

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
            FUZZABLE_DATE,
            FUZZABLE_OBJECT,
            FUZZABLE_MULTIPART_FORMDATA,
            CUSTOM_PAYLOAD,
            CUSTOM_PAYLOAD_HEADER,
            CUSTOM_PAYLOAD_QUERY,
            CUSTOM_PAYLOAD_UUID4_SUFFIX,
            REFRESHABLE_AUTHENTICATION_TOKEN,
            BASEPATH,
            SHADOW_VALUES
        ]
        self.supported_primitive_dict_types = [
            CUSTOM_PAYLOAD,
            CUSTOM_PAYLOAD_HEADER,
            CUSTOM_PAYLOAD_QUERY,
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
        self._value_generators = None
        self._add_examples = True
        self._add_default_value = True

    def _create_fuzzable_dates(self):
        """ Creates dates for future and past, which can be added to a list
        of restler_fuzzable_datetime candidate values

        @return: None
        @rtype : None

        """
        today = datetime.datetime.today()
        # Make sure we add enough days to account for a long fuzzing run
        days_to_add = datetime.timedelta(days = (Settings().time_budget / 24) + 1)
        self._future = today + days_to_add
        self._future_date = self._future.strftime(PAYLOAD_DATE_FORMAT)
        oneday = datetime.timedelta(days=1)
        yesterday = today - oneday
        self._past_date = yesterday.strftime(PAYLOAD_DATE_FORMAT)

    def _get_current_date_from_example(self, example_date, future_date=None):
        """ Takes the example date and returns a date with the same time components
            but with the date after the maximum length of the fuzzing run.
        """
        if example_date is None:
            return example_date

        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
        ]
        # Check if the example contains a date in the above formats.
        # If so, substitute the future date in the same format.
        # Note: currently, this will only work for common formats
        # that start with the date in one of the formats specified above.
        delimiters = [" ", "T"]
        date_part = example_date
        for delim in delimiters:
            if delim in date_part:
                date_part = date_part.split(delim)[0]

        parsed_date = None
        parsed_format_idx = None
        for idx, fmt in enumerate(date_formats):
            try:
                parsed_date = dt.strptime(date_part, fmt)
                parsed_format_idx = idx
            except ValueError:
                pass

        if parsed_date is None:
            return example_date

        future_date = self._future if future_date is None else future_date
        future_date_part = future_date.strftime(date_formats[parsed_format_idx])
        return example_date.replace(date_part, future_date_part)

    def _add_fuzzable_dates(self, candidate_values):
        """ Adds fuzzable dates to a candidate values dict

        @param candidate_values: The candidate values to add the dates to
        @type  candidate_values: Dict

        @return: None
        @rtype : None

        """
        def add_dates(date_primitive):
            candidate_values[date_primitive].values.append(self._future_date)
            candidate_values[date_primitive].values.append(self._past_date)

        if Settings().add_fuzzable_dates:
            if FUZZABLE_DATETIME in candidate_values:
                add_dates(FUZZABLE_DATETIME)
            if FUZZABLE_DATE in candidate_values:
                add_dates(FUZZABLE_DATE)

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

    def get_candidate_values(self, primitive_name, request_id=None, tag=None, quoted=False, examples=[]):
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

        def get_custom_value_generator(value_generator, examples=examples):
            def value_generator_wrapper(done_tracker, generator_idx):
                iter = value_generator(examples=examples)
                count = 0
                while True:
                    try:
                        yield next(iter)
                        count = count + 1
                    except StopIteration:
                        done_tracker[generator_idx] = True
                        # If the count is zero, no values were provided, so exit
                        if count == 0:
                            raise
                        # Reset the iterator
                        iter = value_generator(examples=examples)

            return value_generator_wrapper

        candidate_values = self.candidate_values
        if request_id and request_id in self.per_endpoint_candidate_values:
            candidate_values = self.per_endpoint_candidate_values[request_id]

        # Check if there is a value generator for this primitive name and tag.
        # Note: per-endpoint value generators are not yet implemented
        if self._value_generators:
            candidate_value_gen = None
            if primitive_name in self._value_generators:
                if tag:
                    if tag in self._value_generators[primitive_name]:
                        candidate_value_gen = self._value_generators[primitive_name][tag]
                else:
                    candidate_value_gen = self._value_generators[primitive_name]

            # If there is a value generator, return it.
            if candidate_value_gen:
                return get_custom_value_generator(candidate_value_gen, examples=examples)

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

    def get_fuzzable_values(self, primitive_type, default_value, request_id=None, quoted=False, examples=[]):
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
        @param examples: The available examples for the primitive.
        @type  examples: List[str]

        @return: List of fuzzable values
        @rtype : List[str]

        """
        candidate_values = self.get_candidate_values(primitive_type, request_id,
                                                     quoted=quoted, examples=examples)
        # If the values are dynamically generated, return the generator
        if is_value_generator(candidate_values):
            return candidate_values

        fuzzable_values = list(candidate_values)

        if quoted:
            default_value = f'"{default_value}"'

        if examples and self._add_examples:
            # Use the examples instead of default value

            # Convert the example dates to current dates, if specified
            get_current_date = Settings().add_fuzzable_dates and is_date_type(primitive_type)
            # Quote the example values if needed
            examples_quoted=[]
            for ex_value in examples:
                if get_current_date:
                    ex_value = self._get_current_date_from_example(ex_value)
                if ex_value is None:
                    ex_value = "null"
                elif quoted:
                    ex_value = f'"{ex_value}"'
                examples_quoted.append(ex_value)
            fuzzable_values = examples_quoted + fuzzable_values

        # Only use the default value if no values are defined in
        # the dictionary for that fuzzable type and there are no
        # example values
        if not fuzzable_values and self._add_default_value:
            fuzzable_values.append(default_value)

        # Eliminate duplicates.
        # Note: for the case when a default (non-example) value is in the grammar,
        # the RESTler compiler initializes the dictionary and grammar with the same
        # values.  These duplicates will be eliminated here.
        unique_fuzzable_values = []
        [unique_fuzzable_values.append(x) for x in fuzzable_values if x not in unique_fuzzable_values]

        return unique_fuzzable_values

    def set_value_generators(self, file_path, random_seed=None):
        """ Imports the value generators from the specified module file path.
        """
        attrs = import_utilities.import_attrs(file_path, ["value_generators", "set_random_seed"])
        self._value_generators = attrs[0]
        random_seed_override_fn = attrs[1]
        if random_seed is not None and random_seed_override_fn is not None:
            random_seed_override_fn(random_seed)

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
    examples = None
    param_name = None
    writer_variable = None
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable

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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]

    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    field_name = args[0]
    try:
        enum_vals = args[1]
    except IndexError:
        enum_vals = [""]
    enum_vals = list(map(lambda x: '{}'.format(x), enum_vals))

    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, enum_vals, quoted, examples, param_name, writer_variable


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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable

def restler_fuzzable_date(*args, **kwargs) :
    """ date primitive

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
    # datetime works the same as date
    field_name = args[0]
    quoted = False
    if QUOTED_ARG in kwargs:
        quoted = kwargs[QUOTED_ARG]
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable

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
    examples=[]
    if EXAMPLES_ARG in kwargs:
        examples = kwargs[EXAMPLES_ARG]
    param_name = None
    if PARAM_NAME_ARG in kwargs:
        param_name = kwargs[PARAM_NAME_ARG]
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable

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
    examples = None
    param_name = None
    writer_variable = None
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    examples = None
    param_name = None
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


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
    examples = None
    param_name = None
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable


def restler_custom_payload_query(*args, **kwargs):
    """ Custom payload primitive for query.

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
    examples = None
    param_name = None
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable

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
    examples = None
    param_name = None
    writer_variable = None
    if WRITER_VARIABLE_ARG in kwargs:
        writer_variable = kwargs[WRITER_VARIABLE_ARG]
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable

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
    examples = None
    param_name = None
    writer_variable = None
    return sys._getframe().f_code.co_name, field_name, quoted, examples, param_name, writer_variable

def restler_basepath(*args, **kwargs):
    """ The basepath.

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
    basepath_value = args[0]
    quoted = False
    examples = None
    param_name = None
    writer_variable = None
    return sys._getframe().f_code.co_name, basepath_value, quoted, examples, param_name, writer_variable
