# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Contains BodySchema class that acts as a wrapper for body parameter nodes """
import copy
from collections import namedtuple

from engine.fuzzing_parameters.request_params import *
from engine.fuzzing_parameters.request_schema_parser import *
from engine.fuzzing_parameters.fuzzing_config import *
import utils.logger as logger
import engine.primitives as primitives

class NoSchemaFound(Exception):
    pass

class BodySchemaVisitor():
    """ BodySchemaVisitor Class. """
    def __init__(self):
        # Can be used as an accumulator string while
        # traversing the body schema's params.
        self.val_str = ''
        # Can be used to track the current node depth while traversing
        self.depth = 0

class BodySchema():
    """ Body Schema Class. """

    def __init__(self, request_schema_json=None, fuzzing_config=None, param=None):
        """ Initialize and construct the BodySchema by deserializing the
        compiler generated request schema.

        @param request_schema_json: Compiler generated request schema
        @type  request_schema_json: JSON
        @param fuzzing_config: PayloadBodyChecker specific configuration data (can be None)
        @type  fuzzing_config: Dict
        @param param: Body schema as a ParamObject
        @type  param: ParamObject

        @return: None
        @rtype:  None

        """
        self._schema = param
        # Used by payload body checker
        # Config is used for stateful monitoring while traversing the schema
        self._config = FuzzingConfig(fuzzing_config)

        if request_schema_json:
            try:
                self._set_body_schema(request_schema_json['bodyParameters'])
            except NoSchemaFound:
                raise
            except Exception as err:
                msg = f'Fail deserializing request schema body parameters: {err!s}'
                logger.write_to_main(msg, print_to_console=True)
                raise Exception(msg)

        self._node_count = self._schema.count_nodes(self._config)

    def __eq__(self, other):
        """ Operator equals
        """
        if not isinstance(other, BodySchema):
            # don't attempt to compare against unrelated types
            return False

        return self._schema == other._schema and\
               self._node_count == other._node_count

    def __hash__(self):
        """ Custom hash function """
        return hash(self._schema) + hash(self._node_count)

    @property
    def schema(self) -> ParamObject:
        """ Returns the body schema

        @return: The body schema

        """
        return self._schema

    @schema.setter
    def schema(self, schema: ParamObject):
        """ Sets the schema

        @param schema: The body schema to set
        @return: None

        """
        self._schema = schema

    @property
    def node_count(self) -> int:
        """ Gets the number of nodes in the schema (up to config.max_depth)

        @return: Number of nodes in schema

        """
        return self._node_count

    def set_config(self, config):
        """ Sets config parameters

        @param config: The config object used to set the new config
        @type  config: FuzzingConfig

        """
        # call copy constructor of the config object - will reset statefulness
        self._config = copy.copy(config)
        # Update node count with new schema
        self._node_count = self._schema.count_nodes(self._config)

    def get_blocks(self) -> list:
        """ Returns the request blocks for this schema

        @return: The request blocks for this schema
        @rtype : List[str]

        """
        return self._schema.get_blocks(self._config)

    def get_signature(self) -> str:
        """ Returns the signature of this schema

        @return: The signature of this schema

        """
        return self._schema.get_signature(self._config)

    def get_schema_tag_mapping(self) -> dict:
        """ Returns the schema tag mapping for this schema.

        @return: The schema tag mapping dict
        @rtype : Dictionary format: {"tag": content }

        """
        mapping = dict()
        self._schema.get_schema_tag_mapping(mapping, self._config)
        return mapping

    def get_fuzzing_pool(self, fuzzer, config) -> list:
        """ Returns the fuzzing pool for the schema, created by the fuzzer

        @param fuzzer: The body fuzzer object used for fuzzing and creating the pool
        @type  fuzzer: BodySchemaStructuralFuzzer
        @param config: PayloadBodyChecker specific configuration data (can be None)
        @type  config: Dict

        @return: The fuzzing pool
        @rtype : List[Params]

        """
        # Set the config
        self._config = FuzzingConfig(config)
        # Get the fuzzing pool of the schema
        pool = self._schema.get_fuzzing_pool(fuzzer, self._config)
        body_pool = []
        # For each schema in the pool, create a BodySchema object from it
        # and copy this config to that object.
        for schema in pool:
            body = BodySchema(param=schema)
            body.set_config(self._config)
            body_pool.append(body)
        return body_pool

    def fuzz_body_blocks(self, config) -> list:
        """ Fuzz the value of interpreted body blocks

        @param config: PayloadBodyChecker specific configuration data (can be None)
        @type  config: Dict

        @return: The fuzzed request blocks
        @rtype : List[str]

        """
        # Set the config
        self._config = FuzzingConfig(config)
        # Get the fuzzing blocks
        blocks = self._schema.get_fuzzing_blocks(self._config)

        if self._config.fuzz_strategy == 'restler':
            return [blocks]

        acc = ''
        sets = []

        for block in blocks:
            primitive_type = block[0]
            value = block[1]
            if len(block) > 2:
                quoted = block[2]

            # accumulate
            if primitive_type == primitives.STATIC_STRING:
                if quoted:
                    value = f'"{value}"'
                acc += str(value)

            # fuzzable values
            elif primitive_type == primitives.FUZZABLE_GROUP:
                choices = [f'{acc}{choice}' for choice in value]
                sets.append(choices)
                acc = ''

            # not supported yet
            else:
                logger.raw_network_logging(f'Cannot fuzz type {primitive_type}')
                return blocks

        # tailing static string
        sets.append([acc])

        import engine.fuzzing_parameters.fuzzing_utils as fuzzing_utils
        # compose
        if self._config.fuzz_strategy == 'EX':
            pool = fuzzing_utils.get_product_exhaust(sets, self._config.max_combination)
        elif self._config.fuzz_strategy == 'D1':
            pool = fuzzing_utils.get_product_linear_fair(sets, self._config.max_combination)
        else:
            pool = fuzzing_utils.get_product_linear_bias(sets, self._config.max_combination)

        strs = [''.join(p) for p in pool]
        outs = [[primitives.restler_static_string(string)] for string in strs]
        return outs

    def has_type_mismatch(self, new_body):
        """ Checks the new_body for a type mismatch in one of the nodes
        This is used by the payload body checker for bucketization and logging.

        @param new_body: The body to check for the type mismatch
        @type  new_body: Str

        @return: The node with the mismatched body, or None
        @rtype : Str

        """
        return self._schema.check_type_mismatch(new_body)

    def has_struct_missing(self, new_body):
        """ Check the new_body string for a missing struct
        This is used by the payload body checker for bucketization and logging.

        @param new_body: The body to check for the missing struct, or None
        @type  new_body: Str

        @return: A string representing the missing body pieces
        @rtype : Str

        """
        visitor = BodySchemaVisitor()
        self._schema.check_struct_missing(new_body, visitor)
        return visitor.val_str

    def _set_body_schema(self, body_parameters):
        """ Deserializes and populates the body schema

        @param body_parameters: Body parameters from request schema
        @param body_parameters: JSON

        @return: None
        @rtype : None

        """
        for body_parameter in body_parameters:
            if body_parameter[0] == 'Schema':
                payload = des_body_param(body_parameter[1])
                if payload:
                    self._schema = des_param_payload(payload)
                    return

        raise NoSchemaFound
