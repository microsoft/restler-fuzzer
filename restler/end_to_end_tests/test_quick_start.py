# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Launches demo server and runs restler-quick_start script.
Verifies expected console output and deletes working directory
created during quick start test.

To call: python ./test_quick_start.py <path_to_restler_drop_directory>
"""
import sys
import os
import subprocess
import shutil
from pathlib import Path

RESTLER_WORKING_DIR = 'restler_working_dir'

class QuickStartFailedException(Exception):
    pass

if __name__ == '__main__':
    curr = os.getcwd()
    # Run demo server in background
    os.chdir('demo_server')
    demo_server_path = Path('demo_server', 'app.py')
    demo_server_process = subprocess.Popen([sys.executable, demo_server_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
    os.chdir(curr)

    swagger_path = Path('demo_server', 'swagger.json')
    # argv 1 = path to RESTler drop
    restler_drop_dir = sys.argv[1]

    try:
        # Run the quick start script
        output = subprocess.run(
            f'python ./restler-quick-start.py --api_spec_path {swagger_path} --restler_drop_dir {restler_drop_dir}',
            shell=True, capture_output=True
        )
        # Kill demo server
        demo_server_process.terminate()

        # Check if restler-quick-start succeeded
        if output.stderr:
            raise QuickStartFailedException(f"Failing because stderr was detected after running restler-quick-start:\n{output.stderr!s}")
        try:
            output.check_returncode()
        except subprocess.CalledProcessError:
            raise QuickStartFailedException(f"Failing because restler-quick-start exited with a non-zero return code: {output.returncode!s}")

        stdout = str(output.stdout)
        if 'Request coverage (successful / total): 5 / 6' not in stdout or\
        'No bugs were found.' not in stdout or\
        'Task Test succeeded.' not in stdout:
            stdout = stdout.replace('\\r\\n', '\r\n')
            raise QuickStartFailedException(f"Failing because expected output was not found:\n{stdout}")
    finally:
        # Delete the working directory that was created during restler quick start
        shutil.rmtree(RESTLER_WORKING_DIR)
