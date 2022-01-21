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

            array = ParamArray(values)

            if body_param and name:
                param = ParamMember(name, array, is_required)
            else:
                param = array

            array.tag = f'{next_tag}_array'

        # Object --> ParamObject { ParamMember, ..., ParamMember }
        elif property_type == 'Object':
            members = []
            for member_json in internal_data:
                member = des_param_payload(member_json, tag)
                members.append(member)

            param = ParamObject(members)

            param.tag = f'{next_tag}_object'

        # Property --> ParamMember { name : ParamObject }
        elif property_type == 'Property':
            if len(internal_data) != 1:
                logger.write_to_main(f'Internal Property {name} size != 1')

            value = des_param_payload(internal_data[0], next_tag)

            param = ParamMember(name, value, is_required)

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

        # payload is a dictionary (or member) with size 1
        if len(payload) != 1:
            logger.write_to_main(f'Unexpected payload format {payload}')

        content_type = 'Unknown'
        content_value = 'Unknown'
        custom_payload_type = None
        fuzzable = False
        is_dynamic_object = False

        if 'Fuzzable' in payload:
            content_type = payload['Fuzzable']['primitiveType']
            content_value = payload['Fuzzable']['defaultValue']
            fuzzable = True
        elif 'Constant' in payload:
            content_type = payload['Constant'][0]
            content_value = payload['Constant'][1]
        elif 'DynamicObject' in payload:
            content_type = payload['DynamicObject']['primitiveType']
            content_value = payload['DynamicObject']['variableName']
            is_dynamic_object = True
        elif 'Custom' in payload:
            content_type = payload['Custom']['primitiveType']
            content_value = payload['Custom']['payloadValue']
            custom_payload_type = payload['Custom']['payloadType']

            # TODO: these dynamic objects are not yet supported in the schema.
            # This dictionary is currently not used, and will be used once
            # dynamic objects are added to the schema types below (ParamValue, etc.).
            dynamic_object_input_variable=None
            if 'dynamicObject' in payload['Custom']:
                dynamic_object_input_variable={}
                dynamic_object_input_variable['content_type'] = payload['Custom']['dynamicObject']['primitiveType']
                dynamic_object_input_variable['content_value'] = payload['Custom']['dynamicObject']['variableName']

        elif 'PayloadParts' in payload:
            definition = payload['PayloadParts'][-1]
            if 'Custom' in definition:
                content_type = definition['Custom']['primitiveType']
                content_value = definition['Custom']['payloadValue']
                custom_payload_type = definition['Custom']['payloadType']

        # create value w.r.t. the type
        value = None
        if content_type == 'String' or content_type == 'Uuid' or content_type == 'DateTime':
            # If query parameter, assign as a value and not a string
            # because we don't want to wrap with quotes in the request
            if body_param:
                value = ParamString(custom_payload_type=custom_payload_type, is_required=is_required, is_dynamic_object=is_dynamic_object)
            else:
                value = ParamValue(custom_payload_type=custom_payload_type, is_required=is_required, is_dynamic_object=is_dynamic_object)
        elif content_type == 'Int':
            value = ParamNumber(is_required=is_required, is_dynamic_object=is_dynamic_object)
        elif content_type == 'Number':
            value = ParamNumber(is_required=is_required, is_dynamic_object=is_dynamic_object)
        elif content_type == 'Bool':
            value = ParamBoolean(is_required=is_required, is_dynamic_object=is_dynamic_object)
        elif content_type == 'Object':
            value = ParamObjectLeaf(is_required=is_required, is_dynamic_object=is_dynamic_object)
        elif custom_payload_type is not None and custom_payload_type == 'UuidSuffix':
            value = ParamUuidSuffix(is_required=is_required)
            # Set as unknown for payload body fuzzing purposes.
            # This will be fuzzed as a string.
            value.set_unknown()
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
                value = ParamEnum(contents, enum_content_type, is_required=is_required, body_param=body_param)
            else:
                logger.write_to_main(f'Unexpected enum schema {name}')
        else:
            value = ParamString(False, is_required=is_required, is_dynamic_object=is_dynamic_object)
            value.set_unknown()

        value.set_fuzzable(fuzzable)
        value.content = content_value

        if tag and name:
            value.tag = (tag + '_' + name)
        elif tag:
            value.tag = tag
        else:
            value.tag = name

        # create the param node
        if name:
            param = ParamMember(name, value, is_required=is_required)
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
