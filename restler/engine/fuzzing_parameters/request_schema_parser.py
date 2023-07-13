# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import utils.logger as logger
import collections
from engine.fuzzing_parameters.request_params import *

def des_header_param(header_param_payload):
    """ Deserialize a header parameter payload

    @param header_param_payload: The header parameter payload to deserialize
    @type  header_param_payload: JSON

    @return: Yields HeaderParam objects that represents the header pameters from json
    @rtype : HeaderParam(s)

    """
    headers = des_request_param_payload(header_param_payload)
    for (key, payload) in headers:
        param = des_param_payload(payload, body_param=False)
        if param:
            yield HeaderParam(key, param)
        else:
            return None

def des_query_param(query_param_payload):
    """ Deserialize a query parameter payload

    @param query_param_payload: The query parameter payload to deserialize
    @type  query_param_payload: JSON

    @return: Yields QueryParam objects that represents the query parameters from json
    @rtype : QueryParam(s)

    """
    queries = des_request_param_payload(query_param_payload)
    for (key, payload) in queries:
        param = des_param_payload(payload, body_param=False)
        if param:
            yield QueryParam(key, param)
        else:
            return None

def des_body_param(request_param_payload_json):
    """ Deserializes a body parameter payload

    @param request_param_payload_json: The body parameter payload to deserialize
    @type  request_param_payload_json: JSON

    @return: The body parameter
    @rtype : ParamObject

    """
    des_payload = des_request_param_payload(request_param_payload_json)
    if des_payload:
        des_payload = des_payload[0]
        return des_payload.payload
    return None

def des_request_param_payload(request_param_payload_json):
    """ Deserialize RequestParametersPayload type object.

    @param request_param_payload_json: Request parameter from the compiler
    @type  request_param_payload_json: JSON

    @return: List of tuples containing the keys and payloads
    @rtype:  List[tuple(str, ParamObject)]

    """
    KeyPayload = collections.namedtuple("KeyPayload", ['key', 'payload'])
    payloads = []
    if 'ParameterList' in request_param_payload_json:
        param_list_seq = request_param_payload_json['ParameterList']

        for param_payload_pair in param_list_seq:

            if not ('name' in param_payload_pair and 'payload' in param_payload_pair):
                logger.write_to_main('string - param payload does not contain expected elements')
                raise Exception("Error parsing param payload json.  See the main log for more details.")

            key = param_payload_pair['name']
            payload = param_payload_pair['payload']

            payloads.append(KeyPayload(key, payload))

        return payloads

    return [KeyPayload(None, None)]

def des_dynamic_object(dynobj_json_grammar):
    """Parses dynamic object variable information from the grammar json"""
    primitive_type = dynobj_json_grammar['primitiveType']
    variable_name = dynobj_json_grammar['variableName']
    is_writer = dynobj_json_grammar['isWriter']

    return DynamicObject(primitive_type, variable_name, is_writer)

def des_param_payload(param_payload_json, tag='', body_param=True):
    """ Deserialize ParameterPayload type object.

    @param param_payload_json: Schema for the body, or query or header parameters from the compiler
    @type  param_payload_json: JSON
    @param tag: Node tag
    @type  tag: Str
    @param body_param: Set to True if this is a body parameter
    @type  body_param: Bool

    @return: Body parameter schema
    @rtype:  ParamObject

    """
    param = None
    STRING_CONTENT_TYPES = ['String', 'Uuid', 'DateTime', 'Date']
    param_properties = None

    if 'InternalNode' in param_payload_json:
        internal_node = param_payload_json['InternalNode']
        internal_info = internal_node[0]
        internal_data = internal_node[1]

        name = internal_info['name']
        property_type = internal_info['propertyType']
        if 'isRequired' in internal_info: # check for backwards compatibility of unit test schemas
            is_required = internal_info['isRequired']
        else:
            is_required = True

        if 'isReadOnly' in internal_info: # check for backwards compatibility of old schemas
            is_readonly = internal_info['isReadOnly']
        else:
            is_readonly = False

        param_properties = ParamProperties(is_required=is_required, is_readonly=is_readonly)
        if tag:
            next_tag = tag + '_' + name
        else:
            next_tag = name

        # Array --> ParamMember { name : ParamArray }
        if property_type == 'Array':
            values = []
            for data in internal_data:
                value = des_param_payload(data, next_tag)
                values.append(value)

            array = ParamArray(values, param_properties=param_properties)

            if body_param and name:
                param = ParamMember(name, array, param_properties=param_properties)
            else:
                param = array

            array.tag = f'{next_tag}_array'

        # Object --> ParamObject { ParamMember, ..., ParamMember }
        elif property_type == 'Object':
            members = []
            for member_json in internal_data:
                member = des_param_payload(member_json, tag)
                members.append(member)

            param = ParamObject(members, param_properties=param_properties)

            param.tag = f'{next_tag}_object'

        # Property --> ParamMember { name : ParamObject }
        elif property_type == 'Property':
            if len(internal_data) != 1:
                logger.write_to_main(f'Internal Property {name} size != 1')

            value = des_param_payload(internal_data[0], next_tag)

            param = ParamMember(name, value, param_properties=param_properties)

        # others
        else:
            logger.write_to_main(f'Unknown internal type {property_type}')

    elif 'LeafNode' in param_payload_json:
        leaf_node = param_payload_json['LeafNode']

        name = leaf_node['name']
        payload = leaf_node['payload']
        if 'isRequired' in leaf_node: # check for backwards compatibility of old schemas
            is_required = leaf_node['isRequired']
        else:
            is_required = True

        if 'isReadOnly' in leaf_node: # check for backwards compatibility of old schemas
            is_readonly = leaf_node['isReadOnly']
        else:
            is_readonly = False
        param_properties = ParamProperties(is_required=is_required, is_readonly=is_readonly)

        # payload is a dictionary (or member) with size 1
        if len(payload) != 1:
            logger.write_to_main(f'Unexpected payload format {payload}')

        content_type = 'Unknown'
        content_value = 'Unknown'
        param_name = None
        example_values = []
        custom_payload_type = None
        fuzzable = False
        dynamic_object = None

        if 'Fuzzable' in payload:
            content_type = payload['Fuzzable']['primitiveType']
            content_value = payload['Fuzzable']['defaultValue']
            if 'exampleValue' in payload['Fuzzable']:
                # Workaround for the way null values are serialized to the example
                example_value = payload['Fuzzable']['exampleValue']
                if isinstance(example_value, dict) and 'Some' in example_value.keys() and example_value['Some'] is None:
                    example_value = None
                example_values = [example_value]
            if 'dynamicObject' in payload['Fuzzable']:
                dynamic_object = des_dynamic_object(payload['Fuzzable']['dynamicObject'])
            if 'parameterName' in payload['Fuzzable']:
                param_name = payload['Fuzzable']['parameterName']
            fuzzable = True
        elif 'Constant' in payload:
            content_type = payload['Constant'][0]
            content_value = payload['Constant'][1]
        elif 'DynamicObject' in payload:
            dynamic_object = des_dynamic_object(payload['DynamicObject'])
            content_type = dynamic_object._primitive_type
            content_value = dynamic_object._variable_name
        elif 'Custom' in payload:
            content_type = payload['Custom']['primitiveType']
            content_value = payload['Custom']['payloadValue']
            custom_payload_type = payload['Custom']['payloadType']
            if 'dynamicObject' in payload['Custom']:
                dynamic_object = des_dynamic_object(payload['Custom']['dynamicObject'])
        elif 'PayloadParts' in payload:
            # Note: 'PayloadParts' is no longer supported in the compiler.
            # This code is present to support old grammars, and should be
            # removed with an exception to recompile in the future.
            definition = payload['PayloadParts'][-1]
            if 'Custom' in definition:
                content_type = definition['Custom']['primitiveType']
                content_value = definition['Custom']['payloadValue']
                custom_payload_type = definition['Custom']['payloadType']

        # create value w.r.t. the type
        value = None
        if content_type in STRING_CONTENT_TYPES:
            # Query or header parameter values should not be quoted
            is_quoted = body_param
            if custom_payload_type == "UuidSuffix":
                # Set as unknown for payload body fuzzing purposes.
                # This will be fuzzed as a string.
                value = ParamUuidSuffix(param_properties=param_properties, dynamic_object=dynamic_object,
                                        is_quoted=is_quoted,
                                        content_type=content_type)
                value.set_unknown()
            else:
                value = ParamString(custom_payload_type=custom_payload_type, param_properties=param_properties,
                                    dynamic_object=dynamic_object, is_quoted=is_quoted, content_type=content_type)

        elif content_type == 'Int':
            value = ParamNumber(custom_payload_type=custom_payload_type,
                                param_properties=param_properties,
                                dynamic_object=dynamic_object,
                                number_type=content_type)
        elif content_type == 'Number':
            value = ParamNumber(custom_payload_type=custom_payload_type,
                                param_properties=param_properties,
                                dynamic_object=dynamic_object,
                                number_type=content_type)
        elif content_type == 'Bool':
            value = ParamBoolean(custom_payload_type=custom_payload_type,
                                 param_properties=param_properties,
                                 dynamic_object=dynamic_object)
        elif content_type == 'Object':
            value = ParamObjectLeaf(custom_payload_type=custom_payload_type,
                                    param_properties=param_properties,
                                    dynamic_object=dynamic_object)
        elif 'Enum' in content_type:
            # unique case for Enums, as they are defined as
            # "fuzzable" types in the schema, but are not fuzzable
            # by the same definition as the rest of the fuzzable types.
            fuzzable = False
            # {
            #   Enum : [
            #       name,
            #       type,
            #       [ value1, value2, value3 ],
            #       default_value
            #   ]
            # }
            enum_definition = content_type['Enum']

            if len(enum_definition) == 4:
                enum_name = enum_definition[0]
                enum_content_type = enum_definition[1]
                contents = enum_definition[2]
                # Get quoting depending on the type
                if enum_content_type in STRING_CONTENT_TYPES:
                    is_quoted = body_param
                else:
                    is_quoted = False
                value = ParamEnum(contents, enum_content_type, is_quoted=is_quoted,
                                  custom_payload_type=custom_payload_type,
                                  param_properties=param_properties, enum_name=enum_name)
            else:
                logger.write_to_main(f'Unexpected enum schema {name}')
        else:
            value = ParamString()
            value.set_unknown()

        value.set_fuzzable(fuzzable)
        value.set_example_values(example_values)
        value.set_param_name(param_name)
        value.set_dynamic_object(dynamic_object)
        value.set_content_type(content_type)
        value.content = content_value

        if tag and name:
            value.tag = (tag + '_' + name)
        elif tag:
            value.tag = tag
        else:
            value.tag = name

        # create the param node
        if name:
            param = ParamMember(name, value, param_properties=param_properties)
        else:
            # when a LeafNode represent a standard type, e.g.,
            # string, the name will be empty
            param = value

    else:
        logger.write_to_main('Neither internal nor leaf property')

    if not param:
        logger.write_to_main(f'Fail des param payload {param_payload_json}')
        return None

    return param
