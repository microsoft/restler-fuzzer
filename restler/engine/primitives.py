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
# Types that will be auto-quoted by the engine when extracted from the dictionary
Quoted_Types = {FUZZABLE_STRING, FUZZABLE_DATETIME, FUZZABLE_UUID4, CUSTOM_PAYLOAD}

# The below raw values will be substituted into their non-raw counterparts.
# These values do not correlate to additional primitive types.
FUZZABLE_RAW_STRING = "restler_fuzzable_raw_string"
FUZZABLE_RAW_DATETIME = "restler_fuzzable_raw_datetime"
FUZZABLE_RAW_UUID4 = "restler_fuzzable_raw_uuid4"
CUSTOM_RAW_PAYLOAD = "restler_custom_raw_payload"
Raw_Types = {FUZZABLE_RAW_STRING, FUZZABLE_RAW_DATETIME, FUZZABLE_RAW_UUID4, CUSTOM_RAW_PAYLOAD}

class CandidateValuesPool(object):

    def __init__(self):
        """ Initializes all request primitive types supported by restler.

        @return: None
        @rtype : None

        """
        self.candidate_values = {}

        # Supported primitive types.
        self.supported_primitive_types = [
            STATIC_STRING,
            FUZZABLE_STRING,
            FUZZABLE_RAW_STRING,
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
        for primitive in self.supported_primitive_types:
            self.candidate_values[primitive] = []

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
        DateTime_Str = FUZZABLE_DATETIME
        if DateTime_Str in candidate_values:
            candidate_values[DateTime_Str].append(self._future_date)
            candidate_values[DateTime_Str].append(self._past_date)

    def _set_custom_values(self, to_primitives, from_mutations):
        """ Helper that sets the custom primitive values

        @param to_primitives: The current primitive values that will be updated
                              with the custom values
        @type  to_primitives: Dict
        @param from_mutations: The custom mutations that will be used to update,
                               i.e. from the mutations dictionary
        @type  from_mutations: Dict

        @return: None
        @rtype : None

        """
        for primitive in from_mutations:
            if primitive == 'args':
                continue

            if primitive not in self.get_supported_primitive_types() and\
            primitive not in Raw_Types:
                print(primitive, "not in supported primitives")
                continue

            if primitive in Quoted_Types:
                if isinstance(from_mutations[primitive], dict):
                    # iterate through and update custom payload/dict types
                    for key in from_mutations[primitive].keys():
                        for i, val in enumerate(from_mutations[primitive][key]):
                            from_mutations[primitive][key][i] = f'"{val}"'
                else:
                    for i, val in enumerate(from_mutations[primitive]):
                        from_mutations[primitive][i] = f'"{val}"'
            elif primitive in Raw_Types:
                # ignore raw types for now, we will append these to the matching non-raw
                # collections at the end
                continue

            to_primitives.update({primitive: from_mutations[primitive]})

        for primitive in Raw_Types:
            if primitive in from_mutations:
                # Add the raw values to the matching non-raw collection
                if isinstance(from_mutations[primitive], dict):
                    new_prim = primitive.replace('raw_', '')
                    if not to_primitives[new_prim]:
                        to_primitives[new_prim] = dict()
                    for key in from_mutations[primitive].keys():
                        if key not in to_primitives[new_prim]:
                            to_primitives[new_prim][key] = from_mutations[primitive][key]
                        else:
                            to_primitives[new_prim][key].extend(from_mutations[primitive][key])
                else:
                    to_primitives[primitive.replace('raw_', '')].extend(from_mutations[primitive])

    def get_supported_primitive_types(self):
        """ Returns a list of restler-supported primitive types.

        @return: List of supported primitive type.
        @rtype : List

        """
        return list(self.supported_primitive_types)

    def get_candidate_values(self, primitive_name, request_id=None, tag=None):
        """ Return feasible values for a given primitive.

        @param primitive_name: The primitive whose feasible values we wish to
                                    fetch.
        @type primitive_name: Str
        @param request_id: The request ID of the request to get values for
        @type  request_id: Int

        @return: Feasible values for a given primitive.
        @rtype : List or dict

        """
        def _return_values(val_to_return):
            # return a copy, since this is an accessor
            if isinstance(val_to_return, dict):
                return dict(val_to_return)
            else:
                return list(val_to_return)

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
                    return candidate_values[primitive_name][tag]
                ## tag not in custom, try sending from default
                return self.candidate_values[primitive_name][tag]
            else:
                if primitive_name in candidate_values:
                    return _return_values(candidate_values[primitive_name])
                # primitive values not in custom, try sending from default
                return _return_values(self.candidate_values[primitive_name])
        except KeyError:
            raise CandidateValueException

    def get_fuzzable_values(self, primitive_type, default_value, request_id=None):
        """ Return list of fuzzable values with a default value (specified)
        in the front of the list.

        Note: If default value is already in the list pulled from candidate values
        it will move that value to the front of the list

        @param primitive_type: The type of the primitive to get the fuzzable values for
        @type  primitive_type: Str
        @param default_value: The default value to insert in the front of the list
        @type  default_value: Str
        @param request_id: The request ID of the request to get values for
        @type  request_id: Int

        @return: List of fuzzable values
        @rtype : List[str]

        """
        fuzzable_values = list(
            self.get_candidate_values(primitive_type, request_id)
        )

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
        if 'args' in custom_values:
            if not Settings().settings_file_exists:
                DEPRECATED_set_args(custom_values['args'])

        # Set default primitives
        self._set_custom_values(self.candidate_values, custom_values)
        if not self._dates_added:
            self._add_fuzzable_dates(self.candidate_values)
            self._dates_added = True
        # Set per-resource primitives
        if per_endpoint_custom_mutations:
            for request_id in per_endpoint_custom_mutations:
                self.per_endpoint_candidate_values[request_id] = {}
                for primitive in self.supported_primitive_types:
                    self.per_endpoint_candidate_values[request_id][primitive] = []
                self._set_custom_values(self.per_endpoint_candidate_values[request_id], per_endpoint_custom_mutations[request_id])
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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name

def restler_fuzzable_raw_string(*args, **kwargs):
    """ Fuzzable raw sting primitive.

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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, enum_vals


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name

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
    return sys._getframe().f_code.co_name, field_name

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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name


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
    return sys._getframe().f_code.co_name, field_name

def DEPRECATED_set_args(args):
    """ Sets RestlerSettings values that were specified in the dictionary.

    DEPRECATED - use settings file (see restler_settings.py)
        This is here to support backwards compatibility only, thus the odd design choice
        If settings file was used to set any of these args, use that as priority

    @param args: The args dictionary containing the value to set
    @type  args: Dict

    @return: None
    @rtype : None

    """
    try:
        for arg in args.keys():
            if arg == 'max_combinations':
                    Settings()._max_combinations.set_val(int(args[arg]))

            elif arg == 'namespace_rule_mode':
                if not 'namespacerule' in Settings()._checker_args:
                    Settings()._checker_args.val['namespacerule'] = {}
                Settings()._checker_args.val['namespacerule']['mode'] = str(args[arg])

            elif arg == 'use_after_free_rule_mode':
                use_after_free_rule_mode = args['use_after_free_rule_mode']
                if not 'useafterfree' in Settings()._checker_args:
                    Settings()._checker_args.val['useafterfree'] = {}
                Settings()._checker_args.val['useafterfree']['mode'] = str(args[arg])

            elif arg == 'leakage_rule_mode':
                leakage_rule_mode = args['leakage_rule_mode']
                if not 'leakagerule' in Settings()._checker_args:
                    Settings()._checker_args.val['leakagerule'] = {}
                Settings()._checker_args.val['leakagerule']['mode'] = str(args[arg])

            elif arg == 'resource_hierarchy_rule_mode':
                resource_hierarchy_rule_mode = args['resource_hierarchy_rule_mode']
                if not 'resourcehierarchy' in Settings()._checker_args:
                    Settings()._checker_args.val['resourcehierarchy'] = {}
                Settings()._checker_args.val['resourcehierarchy']['mode'] = str(args[arg])
    except Exception:
        pass
