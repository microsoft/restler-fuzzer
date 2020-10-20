# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import json
import sys
from collections import OrderedDict

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--spec_file',
                        help='Path to spec file',
                        type=str, default=None, required=True)

    args = parser.parse_args()

    try:
        with open(args.spec_file, 'r') as spec_cov:
            spec_json = json.load(spec_cov)
    except Exception as err:
        print(f"Failed to load spec file: {err!s}")

    valid_requests = 0
    invalid_due_to_sequence_failure = 0
    invalid_due_to_resource_failure = 0
    invalid_due_to_parser_failure = 0
    invalid_due_to_500 = 0
    total_requests = len(spec_json)

    # Total each value
    for req in spec_json.values():
        valid_requests += req['valid']
        invalid_due_to_sequence_failure += req['invalid_due_to_sequence_failure']
        invalid_due_to_resource_failure += req['invalid_due_to_resource_failure']
        invalid_due_to_parser_failure += req['invalid_due_to_parser_failure']
        invalid_due_to_500 += req['invalid_due_to_500']

    # Add to json structure
    output = OrderedDict()
    output['final_coverage'] = f'{valid_requests} / {total_requests}'
    output['num_failed_due_to_sequence_failure'] = invalid_due_to_sequence_failure
    output['num_failed_due_to_resource_failure'] = invalid_due_to_resource_failure
    output['num_failed_due_to_parser_failure'] = invalid_due_to_parser_failure
    output['num_failed_due_to_500'] = invalid_due_to_500

    # Output to file
    with open('spec_total.json', 'w') as f_total:
        json.dump(output, f_total, indent=4)


