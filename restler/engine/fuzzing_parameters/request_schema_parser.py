# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import utils.logger as logger
import collections
from engine.fuzzing_parameters.request_params import *

def des_query_param(query_param_payload):
    """ Deserialize a query parameter payload

    @param query_param_payload: The query parameter payload to deserialize
    @type  query_param_payload: JSON

    @return: Yields QueryParam objects that represents the query parameters from json
    @rtype : QueryParam(s)

    """
    queries = des_request_param_payload(query_param_payload)
    for (key, payload) in queries:
        param = des_param_payload(payload, query_param=True)
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
            # pair must have size 2
            if len(param_payload_pair) != 2:
                logger.write_to_main('string - param payload pair size mismatch')
                return [KeyPayload(None, None)]

            key = param_payload_pair[0]
            payload = param_payload_pair[1]

            payloads.append(KeyPayload(key, payload))

        return payloads

    return [KeyPayload(None, None)]

def des_param_payload(param_payload_json, tag='', query_param=False):
    """ Deserialize ParameterPayload type object.

    @param param_payload_json: Body parameter from the compiler
    @type  param_payload_json: JSON
    @param tag: Node tag
    @type  tag: Str
    @param query_param: Set to True if this is a query parameter
    @type  query_param: Bool

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
            if query_param or not name:
                param = array
            else:
                param = ParamMember(name, array)

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

            param = ParamMember(name, value)

        # others
        else:
            logger.write_to_main(f'Unknown internal type {property_type}')

    elif 'LeafNode' in param_payload_json:
        leaf_node = param_payload_json['LeafNode']

        name = leaf_node['name']
        payload = leaf_node['payload']

        # payload is a dictionary (or member) with size 1
        if len(payload) != 1:
            logger.write_to_main(f'Unexpected payload format {payload}')

        content_type = 'Unknown'
        content_value = 'Unknown'
        custom = False
        fuzzable = False

        if 'Fuzzable' in payload:
            content_type = payload['Fuzzable'][0]
            content_value = payload['Fuzzable'][1]
            fuzzable = True
        elif 'Constant' in payload:
            content_type = payload['Constant'][0]
            content_value = payload['Constant'][1]
        elif 'DynamicObject' in payload:
            content_type = 'Unknown'
            content_value = payload['DynamicObject']
        elif 'Custom' in payload:
            custom = True
            content_type = payload['Custom']['payloadType']
            content_value = payload['Custom']['payloadValue']
        elif 'PayloadParts' in payload:
            definition = payload['PayloadParts'][-1]
            if 'Custom' in definition:
                custom = True
                content_type = definition['Custom']['payloadType']
                content_value = definition['Custom']['payloadValue']

        # create value w.r.t. the type
        value = None
        if content_type == 'String':
            # If query parameter, assign as a value and not a string
            # because we don't want to wrap with quotes in the request
            if query_param:
                value = ParamValue(custom=custom)
            else:
                value = ParamString(custom)
        elif content_type == 'DateTime':
            value = ParamString(custom)
        elif content_type == 'Int':
            value = ParamNumber()
        elif content_type == 'Number':
            value = ParamNumber()
        elif content_type == 'Bool':
            value = ParamBoolean()
        elif content_type == 'Object':
            value = ParamObjectLeaf()
        elif content_type == 'UuidSuffix':
            value = ParamUuidSuffix()
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
            #       type,
            #       [ value1, value2, value3 ],
            #       default_value
            #   ]
            # }
            enum_definition = content_type['Enum']

            if len(enum_definition) == 3:
                enum_content_type = enum_definition[0]
                contents = enum_definition[1]
                value = ParamEnum(contents, enum_content_type)
            else:
                logger.write_to_main(f'Unexpected enum schema {name}')
        else:
            value = ParamString(False)
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
            param = ParamMember(name, value)
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