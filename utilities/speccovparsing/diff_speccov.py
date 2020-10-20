# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import sys
import argparse
from collections import OrderedDict

def diff_reqs(left_req, right_req):
    """ Diffs two request dicts.

    @return: A dict containing any differences between the two request
             dicts that were passed as arguments to this function.

             Example format:
             {
                "valid": {
                    "left" : 0,
                    "right": 1
                }
            }
    """
    if set(left_req.keys()) != set(right_req.keys()):
        print("WARNING: Request coverage keys do not match! File formats are not equal!")

    diffs = {}
    # Iterate through the left_req keys and compare the two requests' values.
    # NOTE: Any differences in keys here will either cause a failure or be
    # ignored. The files are expected to have matching formats.
    for key in left_req.keys():
        try:
            if (type(left_req[key]) != type(right_req[key]))\
            or left_req[key] != right_req[key]:
                diffs[key] = {
                    "left": left_req[key],
                    "right": right_req[key]
                }
        except KeyError:
            print(f"Key, {key}, not found in right file's request!")

    return diffs

def diff_files(left_file, right_file):
    """ Diffs two speccov json files.
    Inputs are deserialized JSON objects.

    @return: An OrderedDict containing the diffs of each file.

        Example format:
        {
            "METHOD endpoint": {
                "valid": {
                    "left" : 0,
                    "right": 1
                }
            }
        }

    """
    diffs = OrderedDict()
    # Iterate through each request in the left file and diff its contents
    # with the matching request in the right file
    for req_id in left_file.keys():
        if req_id in right_file:
            req_diff = diff_reqs(left_file[req_id], right_file[req_id])
            # If there were any differences add it to the diff dict
            if req_diff:
                diffs[left_file[req_id]['verb_endpoint']] = req_diff

    # Check for any additional requests in either the left or right file
    left_only = set(left_file.keys()).difference(set(right_file.keys()))
    right_only = set(right_file.keys()).difference(set(left_file.keys()))

    if left_only:
        diffs['requests_left_only'] = [left_file[key]["verb_endpoint"] for key in left_only]
    if right_only:
        diffs['requests_right_only'] = [right_file[key]["verb_endpoint"] for key in right_only]

    return diffs

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--left_file',
                        help='Spec file to diff against.',
                        type=str, default=None, required=True)
    parser.add_argument('--right_files',
                        help='List of spec files to diff with left_file.',
                        type=str, nargs='+', required=True)
    parser.add_argument('--output_file',
                        help='Filename for output file.',
                        type=str, default=None, required=False)

    args = parser.parse_args()

    try:
        with open(args.left_file, 'r') as spec_cov:
            left_json = json.load(spec_cov)
    except Exception as err:
        print(f"Failed to load left file: {err!s}")
        sys.exit(-1)

    output = []
    for spec in args.right_files:
        try:
            with open(spec, 'r') as spec_file:
                right_json = json.load(spec_file)
        except Exception as err:
            print(f"Failed to load right file {spec}: {err!s}.\n"
                   "Skipping diff for this file!")
            continue

        diff = diff_files(left_json, right_json)
        if diff:
            output.append(spec)
            output.append(diff)

    output_file = args.output_file or 'spec_diffs.json'
    with open(output_file, 'w') as f_diffs:
        json.dump(output, f_diffs, indent=4)


