# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import argparse
import contextlib
import os
import subprocess
from pathlib import Path

RESTLER_TEMP_DIR = 'restler_working_dir'

@contextlib.contextmanager
def usedir(dir):
    """ Helper for 'with' statements that changes the current directory to
    @dir and then changes the directory back to its original once the 'with' ends.

    Can be thought of like pushd with an auto popd after the 'with' scope ends
    """
    curr = os.getcwd()
    os.chdir(dir)
    try:
        yield
    finally:
        os.chdir(curr)

def compile_spec(api_spec_path, restler_dll_path):
    """ Compiles a specified api spec

    @param api_spec_path: The absolute path to the Swagger file to compile
    @type  api_spec_path: Str
    @param restler_dll_path: The absolute path to the RESTler driver's dll
    @type  restler_dll_path: Str

    @return: None
    @rtype : None

    """
    if not os.path.exists(RESTLER_TEMP_DIR):
        os.makedirs(RESTLER_TEMP_DIR)

    with usedir(RESTLER_TEMP_DIR):
        command=f"dotnet \"{restler_dll_path}\" compile --api_spec \"{api_spec_path}\""
        print(f"command: {command}")
        subprocess.run(command, shell=True)

def add_common_settings(ip, port, host, use_ssl, command):
    if not use_ssl:
        command = f"{command} --no_ssl"
    if ip is not None:
        command = f"{command} --target_ip {ip}"
    if port is not None:
        command = f"{command} --target_port {port}"
    if host is not None:
        command = f"{command} --host {host}"
    return command

def replay_bug(ip, port, host, use_ssl, restler_dll_path, replay_log):
    """ Runs RESTler's replay mode on the specified replay file
    """
    with usedir(RESTLER_TEMP_DIR):
        command = (
            f"dotnet \"{restler_dll_path}\" replay --replay_log \"{replay_log}\""
        )
        command = add_common_settings(ip, port, host, use_ssl, command)
        print(f"command: {command}\n")
        subprocess.run(command, shell=True)

def replay_from_dir(ip, port, host, use_ssl, restler_dll_path, replay_dir):
    import glob
    from pathlib import Path
    # get all the 500 replay files in the bug buckets directory
    bug_buckets = glob.glob(os.path.join(replay_dir, 'RestlerResults', '**/bug_buckets/*500*.replay.txt'))
    print(f"buckets: {bug_buckets}")
    for file_path in bug_buckets:
        if "bug_buckets" in os.path.basename(file_path):
            continue
        print(f"Testing replay file: {file_path}")
        replay_bug(ip, port, host, use_ssl, restler_dll_path, Path(file_path).absolute())
    pass

def test_spec(ip, port, host, use_ssl, restler_dll_path, task):
    """ Runs RESTler's test mode on a specified Compile directory

    @param ip: The IP of the service to test
    @type  ip: Str
    @param port: The port of the service to test
    @type  port: Str
    @param host: The hostname of the service to test
    @type  host: Str
    @param use_ssl: If False, set the --no_ssl parameter when executing RESTler
    @type  use_ssl: Boolean
    @param restler_dll_path: The absolute path to the RESTler driver's dll
    @type  restler_dll_path: Str

    @return: None
    @rtype : None

    """
    import json
    with usedir(RESTLER_TEMP_DIR):
        compile_dir = Path(f'Compile')
        grammar_file_path = compile_dir.joinpath('grammar.py')
        dictionary_file_path = compile_dir.joinpath('dict.json')
        settings_file_path = compile_dir.joinpath('engine_settings.json')

        command = (
            f"dotnet \"{restler_dll_path}\" {task} --grammar_file \"{grammar_file_path}\" --dictionary_file \"{dictionary_file_path}\""
            f" --settings \"{settings_file_path}\""
        )
        print(f"command: {command}\n")
        command = add_common_settings(ip, port, host, use_ssl, command)

        subprocess.run(command, shell=True)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--api_spec_path',
                        help='The API Swagger specification to compile and test',
                        type=str, required=False, default=None)
    parser.add_argument('--ip',
                        help='The IP of the service to test',
                        type=str, required=False, default=None)
    parser.add_argument('--port',
                        help='The port of the service to test',
                        type=str, required=False, default=None)
    parser.add_argument('--restler_drop_dir',
                        help="The path to the RESTler drop",
                        type=str, required=True)
    parser.add_argument('--use_ssl',
                        help='Set this flag if you want to use SSL validation for the socket',
                        action='store_true')
    parser.add_argument('--host',
                        help='The hostname of the service to test',
                        type=str, required=False, default=None)
    parser.add_argument('--task',
                        help='The task to run (test, fuzz-lean, fuzz, or replay)'
                             'For test, fuzz-lean, and fuzz, the spec is compiled first.'
                             'For replay, bug buckets from the specified task directory are re-played.',
                        type=str, required=False, default='test')
    parser.add_argument('--replay_bug_buckets_dir',
                        help='For the replay task, specifies the directory in which to search for bug buckets.',
                        type=str, required=False, default=None)

    args = parser.parse_args()
    restler_dll_path = Path(os.path.abspath(args.restler_drop_dir)).joinpath('restler', 'Restler.dll')
    print(f"\nrestler_dll_path: {restler_dll_path}\n")

    if args.task == "replay":
        replay_from_dir(args.ip, args.port, args.host, args.use_ssl, restler_dll_path.absolute(), args.replay_bug_buckets_dir)
    else:
        if args.api_spec_path is None:
            print("api_spec_path is required for all tasks except the replay task.")
            exit(-1)
        api_spec_path = os.path.abspath(args.api_spec_path)
        compile_spec(api_spec_path, restler_dll_path.absolute())
        test_spec(args.ip, args.port, args.host, args.use_ssl, restler_dll_path.absolute(), args.task)

    print(f"Test complete.\nSee {os.path.abspath(RESTLER_TEMP_DIR)} for results.")
