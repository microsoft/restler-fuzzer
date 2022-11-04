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
import signal
import time
import subprocess
import shutil
import glob
import json
from pathlib import Path
from threading import Thread

RESTLER_WORKING_DIR = 'restler_working_dir'

class QuickStartFailedException(Exception):
    pass

def check_output_errors(output):
    if output.stderr:
        raise QuickStartFailedException(f"Failing because stderr was detected after running restler-quick-start:\n{output.stderr!s}")
    try:
        output.check_returncode()
    except subprocess.CalledProcessError:
        raise QuickStartFailedException(f"Failing because restler-quick-start exited with a non-zero return code: {output.returncode!s}")

def check_expected_output(restler_working_dir, expected_strings, output, task_dir_name):
    stdout = str(output.stdout)

    for expected_str in expected_strings:
        if expected_str not in stdout:
            stdout = stdout.replace('\\r\\n', '\r\n')

            # Print the engine logs to the console
            out_file_path = os.path.join(restler_working_dir, task_dir_name, 'EngineStdOut.txt')
            err_file_path = os.path.join(restler_working_dir, task_dir_name, 'EngineStdErr.txt')
            results_dir = os.path.join(restler_working_dir, task_dir_name, 'RestlerResults')
            # Return the newest experiments directory in RestlerResults
            net_log_dir = max(glob.glob(os.path.join(results_dir, 'experiment*/')), key=os.path.getmtime)
            net_log_path = glob.glob(os.path.join(net_log_dir, 'logs', f'network.testing.*.1.txt'))[0]
            with open(out_file_path) as of, open(err_file_path) as ef, open(net_log_path) as nf:
                out = of.read()
                err = ef.read()
                net_log = nf.read()
            raise QuickStartFailedException(f"Failing because expected output '{expected_str}' was not found:\n{stdout}{out}{err}{net_log}")

def test_test_task(restler_working_dir, swagger_path, restler_drop_dir):
    # Run the quick start script
    output = subprocess.run(
        f'python ./restler-quick-start.py --api_spec_path {swagger_path} --restler_drop_dir {restler_drop_dir} --task test',
        shell=True, capture_output=True
    )
    expected_strings = [
        'Request coverage (successful / total): 6 / 6',
        'Attempted requests: 6 / 6',
        'No bugs were found.',
        'Task Test succeeded.'
    ]
    check_output_errors(output)
    check_expected_output(restler_working_dir, expected_strings, output, "Test")


def test_test_task_low_coverage(restler_working_dir, swagger_path, restler_drop_dir):
    # Mutate the specification so there are coverage errors
    def mutate_spec(new_swagger_path):
        new_swagger_spec = json.load(open(swagger_path, encoding='utf-8'))
        # Modify the example, which will cause the POST request to fail
        new_swagger_spec['components']['schemas']['BlogPostPublicInput']['example']['id'] = 1

        json.dump(new_swagger_spec,  open(new_swagger_path, "w", encoding='utf-8'), indent=2)

    new_swagger_path = os.path.join(Path(swagger_path).parent, "mutated_swagger_low_coverage.json")

    try:
        mutate_spec(new_swagger_path)

        # Run the quick start script
        output = subprocess.run(
            f'python ./restler-quick-start.py --api_spec_path {new_swagger_path} --restler_drop_dir {restler_drop_dir} --task test',
            shell=True, capture_output=True
        )
        expected_strings = [
            'Request coverage (successful / total): 2 / 6',
            'Attempted requests: 3 / 6',
            'No bugs were found.',
            'Task Test succeeded.'
        ]
        check_output_errors(output)
        check_expected_output(restler_working_dir, expected_strings, output, "Test")

        baseline_coverage_txt_path = os.path.join(restler_working_dir, "..", "restler",
                                                  "end_to_end_tests", "baselines",
                                                  "mutated_swagger_coverage_failures.txt")
        actual_coverage_txt_path = os.path.join(restler_working_dir, "Test", "coverage_failures_to_investigate.txt")
        def result_filter(line):
            return "Request:" in line or "Number of blocked dependent requests" in line

        with open(baseline_coverage_txt_path, "r") as bf, open(actual_coverage_txt_path, "r") as af:
            expected_lines = list(filter(result_filter, bf.readlines()))
            actual_lines = list(filter(result_filter, af.readlines()))

            if actual_lines != expected_lines:
                raise QuickStartFailedException(f"Failing because coverage txt baselines do not match.")
            else:
                print("Coverage txt baselines match.")
    finally:
        # Delete the mutated spec
        if os.path.exists(new_swagger_path):
            os.remove(new_swagger_path)


def test_fuzzlean_task(restler_working_dir, swagger_path, restler_drop_dir):
    # Run the quick start script
    output = subprocess.run(
        f'python ./restler-quick-start.py --api_spec_path {swagger_path} --restler_drop_dir {restler_drop_dir} --task fuzz-lean',
        shell=True, capture_output=True
    )
    expected_strings = [
        'Request coverage (successful / total): 6 / 6',
        'Attempted requests: 6 / 6',
        'Bugs were found!' ,
        'InvalidDynamicObjectChecker_20x: 2',
        'PayloadBodyChecker_500: 2',
        'UseAfterFreeChecker_20x: 1',
        'InvalidValueChecker_500: 1',
        'Task FuzzLean succeeded.'
    ]
    check_output_errors(output)
    check_expected_output(restler_working_dir, expected_strings, output, "FuzzLean")

def test_fuzz_task(restler_working_dir, swagger_path, restler_drop_dir):
    import json
    compile_dir = Path(restler_working_dir, f'Compile')
    settings_file_path = compile_dir.joinpath('engine_settings.json')
    # Set the maximum number of generations (i.e. sequence length) to limit fuzzing
    settings_json=json.load(open(settings_file_path))
    settings_json["max_sequence_length"] = 5
    json.dump(settings_json, open(settings_file_path, "w", encoding='utf-8'))

    expected_strings = [
        'Request coverage (successful / total): 6 / 6',
        'Attempted requests: 6 / 6',
        'Bugs were found!' ,
        'InvalidDynamicObjectChecker_20x: 2',
        'InvalidDynamicObjectChecker_500: 1',
        'PayloadBodyChecker_500: 1',
        'InvalidValueChecker_500: 1',
        'Task Fuzz succeeded.'
    ]
    output = subprocess.run(
        f'python ./restler-quick-start.py --api_spec_path {swagger_path} --restler_drop_dir {restler_drop_dir} --task fuzz',
        shell=True, capture_output=True
    )
    check_output_errors(output)
    # check_expected_output(restler_working_dir, expected_strings, output)

def test_replay_task(restler_working_dir, task_output_dir, restler_drop_dir):
    # Run the quick start script
    print(f"Testing replay for bugs found in task output dir: {task_output_dir}")
    output = subprocess.run(
        f'python ./restler-quick-start.py --replay_bug_buckets_dir {task_output_dir} --restler_drop_dir {restler_drop_dir} --task replay',
        shell=True, capture_output=True
    )
    check_output_errors(output)
    # Check that the Replay directory is present and that it contains a bug bucket with the
    # same bug.
    original_bug_buckets_file_path = glob.glob(os.path.join(task_output_dir, 'RestlerResults/*/bug_buckets/bug_buckets.txt'))[0]

    # TODO: it would be better if the replay command also produced a bug bucket, so they could be
    # diff'ed with the original bug buckets.
    # Until this is implemented, check that a 500 is found in the log.
    # replay_buckets = glob.glob(os.path.join(restler_working_dir, 'Replay/RestlerResults/*/bug_buckets/bug_buckets.txt'))
    network_log = glob.glob(os.path.join(restler_working_dir, 'Replay/RestlerResults/**/logs/network.*.txt'))
    if network_log:
        network_log = network_log[0]
    else:
        output = str(output.stdout)
        raise QuickStartFailedException(f"No bug buckets were found after replay.  Output: {output}")

    with open(network_log) as rf, open(original_bug_buckets_file_path) as of:
        orig_buckets = of.read()
        log_contents = rf.read()
        if 'HTTP/1.1 500 Internal Server Error' not in log_contents:
            raise QuickStartFailedException(f"Failing because bug buckets {orig_buckets} were not reproduced.  Replay log: {log_contents}.")
        else:
            print("500 error was reproduced.")

demo_server_output=[]

def get_demo_server_output(demo_server_process):
    demo_server_output.clear()
    while demo_server_process.poll() is None:
        output,_ = demo_server_process.communicate()

        if output:
            demo_server_output.append(output)


if __name__ == '__main__':
    curr = os.getcwd()

    # Run demo server in background
    # Note: demo_server must be started in its directory
    os.chdir('demo_server')
    demo_server_path = Path('demo_server', 'app.py')
    if hasattr(os.sys, 'winver'):
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        creationflags = 0

    demo_server_process = subprocess.Popen([sys.executable, demo_server_path],
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            creationflags=creationflags)
    thread = Thread(target = get_demo_server_output, args = (demo_server_process, ))
    thread.start()

    os.chdir(curr)

    swagger_path = Path('demo_server', 'swagger.json')
    # argv 1 = path to RESTler drop
    restler_drop_dir = sys.argv[1]
    restler_working_dir = os.path.join(curr, RESTLER_WORKING_DIR)
    test_failed = False
    try:
        print("+++++++++++++++++++++++++++++test...")
        test_test_task(restler_working_dir, swagger_path, restler_drop_dir)

        print("+++++++++++++++++++++++++++++test with coverage errors...")
        test_test_task_low_coverage(restler_working_dir, swagger_path, restler_drop_dir)

        print("+++++++++++++++++++++++++++++fuzzlean...")
        test_fuzzlean_task(restler_working_dir, swagger_path, restler_drop_dir)

        print("+++++++++++++++++++++++++++++replay...")
        fuzzlean_task_dir = os.path.join(curr, RESTLER_WORKING_DIR, 'FuzzLean')
        test_replay_task(restler_working_dir, fuzzlean_task_dir, restler_drop_dir)

        #print("+++++++++++++++++++++++++++++fuzz...")
        #test_fuzz_task(restler_working_dir, swagger_path, restler_drop_dir)

    except Exception as exn:
        test_failed = True
        raise
    finally:
        # Kill demo server
        if hasattr(os.sys, 'winver'):
            os.kill(demo_server_process.pid, signal.CTRL_BREAK_EVENT)
        else:
            demo_server_process.send_signal(signal.SIGTERM)
        print("done terminating demo_server process")

        thread.join()
        if test_failed:
            print(f"Demo server output: {demo_server_output}.")

        print("The End.")

        # Delete the working directory that was created during restler quick start
        shutil.rmtree(RESTLER_WORKING_DIR)

