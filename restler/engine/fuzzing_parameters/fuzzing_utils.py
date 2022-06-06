# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import print_function

import itertools
import json

import engine.primitives as primitives

def get_product_exhaust(sets, bound):
    """ Return the product of the input sets exhaustively

    @param sets: Input sets
    @type  sets: List
    @param bound: Max number of the product
    @type  bound: Int

    @return: Product (partial) of the input sets
    @rtype:  List

    """
    # default depth-first Cartesian product
    combination = itertools.product(*sets)
    combination = itertools.islice(combination, bound)

    return [list(tu) for tu in combination]


def get_product_linear_bias(sets, bound):
    """ Return the product of the input sets (1-D combinatorial)

    @param sets: Input sets
    @type  sets: List
    @param bound: Max number of the product
    @type  bound: Int

    @return: Product (partial) of the input sets
    @rtype:  List

    """
    # check not empty set
    for s in sets:
        if not s:
            return []

    # use the first element as default
    product = [[s[0] for s in sets]]
    cnt = 1

    for idx, si in enumerate(sets):
        # pre
        pre = [s[0] for s in sets[:idx]]
        # post
        post = [s[0] for s in sets[idx + 1:]]
        # pivot
        for pivot in si[1:]:
            if (cnt < bound) or (bound < 0):
                product.append(pre + [pivot] + post)
                cnt += 1
            else:
                return product

    return product


def get_product_linear_fair(sets, bound):
    """ Return the product of the input sets (1-D combinatorial) in
    breadth-first order.

    @param sets: Input sets
    @type  sets: List
    @param bound: Max number of the product
    @type  bound: Int

    @return: Product (partial) of the input sets
    @rtype:  List

    """
    for s in sets:
        if not s:
            return []

    product = [[s[0] for s in sets]]
    cnt = 1

    ptrs = [1] * len(sets)

    while (cnt < bound) or (bound < 0):
        done = True

        for idx, si in enumerate(sets):
            # pre
            pre = [s[0] for s in sets[:idx]]
            # post
            post = [s[0] for s in sets[idx + 1:]]
            # pivot
            if ptrs[idx] < len(si):
                pivot = si[ptrs[idx]]
                ptrs[idx] += 1
                cnt += 1
                product.append(pre + [pivot] + post)

            if ptrs[idx] < len(si):
                done = False

        if done:
            break

    if (bound > 0) and (len(product) > bound):
        return product[:bound]

    return product


def flatten_json_object(hier_json):
    """ Flatten the JSON ojbect

    @param hier_json: Input JSON ojbect (with hierarchy)
    @type  hier_json: JSON

    @return: Tag/values mapping
    @rtype:  Dict

    """
    flat_dict = {}

    def flatten(x, name=''):
        if isinstance(x, dict):
            for a in x:
                flatten(x[a], name + a + '_')
        elif isinstance(x, list):
            flat_dict[name[:-1]] = x
            for a in x:
                flatten(a, name)
        else:
            flat_dict[name[:-1]] = x

    flatten(hier_json)
    return flat_dict


def get_response_body(response):
    """ Return the response body

    @param response: Input response string
    @type  response: String

    @return: Response body
    @rtype:  JSON

    """
    from engine.transport_layer.messaging import DELIM
    # sanity cleanup
    response = response.replace('\\"', "'")
    response = response.replace("\\'", "'")
    response = response.replace("\'", "'")

    # extract the response body by separating at the known delimiter
    # Ex: METHOD /end/point HTTP/1.1 DELIM{}
    body_start = response.find(DELIM)
    if body_start == -1:
        return None

    # Save the index where the body begins
    body_start = body_start + len(DELIM)

    try:
        start_char = response[body_start]
    except Exception:
        return None

    if start_char == '{':
        end_char = '}'
    elif start_char == '[':
        end_char = ']'
    else:
        return None

    body_end = response.rfind(end_char)
    if body_end == -1 or body_end < body_start:
        return None

    try:
        body_str = response[body_start: body_end + 1]
        body = json.loads(body_str)
        return body

    # IndexError or json loads error
    except Exception:
        return None


def replace_number_chunks(msg, tar='?'):
    """ Replace digits and adjacent alphabets with the given term

    @param msg: Input message
    @type  msg: String
    @param tar: New term to replace
    @type  tar: String

    @return: Replaced message
    @rtype:  String

    """
    def find_first_digit(msg):
        for i, c in enumerate(msg):
            if c.isdigit():
                return i
        return -1

    def find_prev_escape(msg, idx):
        for i, c in reversed(list(enumerate(msg[:idx]))):
            if not c.isdigit() and not c.isalpha():
                return i
        return 0

    def find_next_escape(msg, idx):
        for i, c in enumerate(msg[idx + 1:]):
            if not c.isdigit() and not c.isalpha():
                return i + idx + 1
        return -1

    for _ in range(50):
        digit_idx = find_first_digit(msg)
        if digit_idx == -1:
            return msg

        prev_idx = find_prev_escape(msg, digit_idx)
        next_idx = find_next_escape(msg, digit_idx)

        if next_idx == -1:
            msg = msg[:prev_idx + 1] + tar
        else:
            msg = msg[:prev_idx + 1] + tar + msg[next_idx:]

    return msg

