# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
import engine.primitives as primitives

class FuzzingConfig(object):
    def __init__(self, config_json=None):
        """ FuzzingConfig constructor

        @param config_json: PayloadBodyChecker specific configuration data
        @type  config_json: Dict

        """
        self.use_examples_for_default = False
        self.use_response_for_default = False
        self.use_embedded = False
        self.use_wordbook = True
        self.use_examples = False
        self.use_response = False
        self.get_wordbook_values = None
        self.get_examples_values = None
        self.get_response_values = None
        self.fuzz_strategy = 'restler'
        self.max_combination = 100
        self.merge_fuzzable_values = False
        self.max_depth = sys.maxsize
        # Traversal depth state
        self.depth = 0

        # config_json used by payload body checker only.
        # Some values may be set to payload body checker defaults
        # if the config exists.
        if config_json:
            if 'use_examples_for_default' in config_json:
                self.use_examples_for_default = config_json['use_examples_for_default']
            if 'use_response_for_default' in config_json:
                self.use_response_for_default = config_json['use_response_for_default']

            if 'use_embedded_for_fuzzable' in config_json:
                self.use_embedded = config_json['use_embedded_for_fuzzable']
            if 'use_wordbook_for_fuzzable' in config_json:
                self.use_wordbook = config_json['use_wordbook_for_fuzzable']
            if 'use_examples_for_fuzzable' in config_json:
                self.use_examples = config_json['use_examples_for_fuzzable']
            if 'use_response_for_fuzzable' in config_json:
                self.use_response = config_json['use_response_for_fuzzable']

            if 'get_wordbook_values' in config_json:
                self.get_wordbook_values = config_json['get_wordbook_values']
            if 'get_examples_values' in config_json:
                self.get_examples_values = config_json['get_examples_values']
            if 'get_response_values' in config_json:
                self.get_response_values = config_json['get_response_values']

            if 'fuzz_strategy' in config_json:
                self.fuzz_strategy = config_json['fuzz_strategy']
            if 'max_combination' in config_json:
                self.max_combination = config_json['max_combination']
            if 'max_depth' in config_json:
                self.max_depth = config_json['max_depth']
            else:
                self.max_depth = 10

            if self.use_examples or self.use_response or self.use_embedded:
                self.merge_fuzzable_values = True
            elif self.fuzz_strategy != 'restler':
                self.merge_fuzzable_values = True
            else:
                self.merge_fuzzable_values = False

    def __copy__(self):
        """ Copy constructor. Resets stateful variables. """
        new_config = FuzzingConfig()

        new_config.use_examples_for_default = self.use_examples_for_default
        new_config.use_response_for_default = self.use_response_for_default
        new_config.use_embedded = self.use_embedded
        new_config.use_wordbook = self.use_wordbook
        new_config.use_examples = self.use_examples
        new_config.use_response = self.use_response
        new_config.get_wordbook_values = self.get_wordbook_values
        new_config.get_examples_values = self.get_examples_values
        new_config.get_response_values = self.get_response_values
        new_config.fuzz_strategy = self.fuzz_strategy
        new_config.max_combination = self.max_combination
        new_config.merge_fuzzable_values = self.merge_fuzzable_values
        new_config.max_depth = self.max_depth

        return new_config

    def get_default_value(self, tag, primitive_type, hint=None):
        """ Return a default value of a parameter by searching from
        examples/response

        @param tag: Parameter tag
        @type  tag: String
        @param primitive_type: Primitive type
        @type  primitive_type: String

        @return: Default value
        @rtype:  String/Int/Dict

        """
        # initialize
        default_value = self.get_default_value_of_type(primitive_type)

        # use example value as default (if exist)
        if self.use_examples_for_default and self.get_examples_values:
            examples_values = self.get_examples_values(tag)
            if examples_values:
                default_value = list(examples_values)[0]

        # use response value as default (if exist)
        if self.use_response_for_default and self.get_response_values:
            response_values = self.get_response_values(tag, hint)
            if response_values:
                default_value = response_values[0]

        return default_value

    def get_default_value_of_type(self, primitive_type):
        """ Return a default value for the primitive type as a json
        serialized string

        @param primitive_type: Primitive type
        @type  primitive_type: String

        @return: Default value
        @rtype:  String

        """
        if primitive_type == primitives.FUZZABLE_STRING:
            return 'fuzzstring'
        elif primitive_type == primitives.FUZZABLE_INT:
            return '0'
        elif primitive_type == primitives.FUZZABLE_BOOL:
            return 'false'
        elif primitive_type == primitives.FUZZABLE_OBJECT:
            return '{ "fuzz" : false }'
        else:
            logger.raw_network_logging(f'Unknown type {primitive_type} for default')
            return 'null'

    def get_fuzzable_values(self, tag, primitive_type):
        """ Return a list of fuzzable values of a parameter by searching from
        examples/response/wordbook

        @param tag: Parameter tag
        @type  tag: String
        @param primitive_type: Parameter primitive type
        @type  primitive_type: String

        @return: A list of fuzzable values
        @rtype:  List

        """
        # initialize
        fuzzable_values = []

        # add examples values
        if self.use_examples and self.get_examples_values:
            fuzzable_values += self.get_examples_values(tag)

        # add response values
        if self.use_response and self.get_response_values:
            fuzzable_values += self.get_response_values(tag)

        # add wordbook values
        if self.use_wordbook and self.get_wordbook_values:
            fuzzable_values += self.get_wordbook_values(primitive_type)

        # add the default value
        if self.use_embedded:
            fuzzable_values += [
                self.get_default_value_of_type(primitive_type)]

        return fuzzable_values

    def cleanup_fuzzable_group(self, default_value, fuzzable_values):
        """ Remove redundant fuzzable values and put default at first place

        @param default_value: Default value
        @type  default_value: String
        @param fuzzable_values: A list of fuzzable values
        @type  fuzzable_values: List

        @return: Clean fuzzable group
        @rtype:  List

        """
        # remove overlapping values
        x = set(fuzzable_values)
        if default_value in x:
            x.remove(default_value)
        return [default_value] + list(x)