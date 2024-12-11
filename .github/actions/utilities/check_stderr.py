# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import sys
import os

def check_log_file(log_file):
    if not os.path.exists(log_file):
        print(f"Stderr log file not found: {log_file}")
        sys.exit(-1)
    
    with open(log_file, 'r') as file:
        content = file.read()
        if content:
            print(content)
            sys.exit(1)
        else:
            print("Stderr log file is empty.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_log_file.py <log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    check_log_file(log_file)
