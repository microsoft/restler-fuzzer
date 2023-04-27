# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import json

from test_servers.parsed_requests import *
from test_servers.log_parser import *

if __name__ == '__main__':
    # Add an argument for the left file and right file
    parser = argparse.ArgumentParser()
    parser.add_argument('--left_file', help='Path to left file', type=str, default=None, required=True)
    parser.add_argument('--right_file', help='Path to right file', type=str, default=None, required=True)
    parser.add_argument('--output_file',
                        help='Filename for output file.',
                        type=str, default=None, required=False)
    args = parser.parse_args()

    # Compare the two files using NetworkLogParser
    print("Parsing left file...")
    left_parser = FuzzingLogParser(args.left_file)
    # TODO: output a summary of what was found in the left file (# sequences, requests, etc.)

    print("Parsing right file...")
    right_parser = FuzzingLogParser(args.right_file)
    # TODO: output a summary of what was found in the left file (# sequences, requests, etc.)

    diff = left_parser.diff_log(right_parser)

    # Write the diff to a file
    output_file = args.output_file or 'network_log_diffs.json'
    with open(output_file, 'w') as f_diffs:
        json.dump(diff, f_diffs, indent=4)
