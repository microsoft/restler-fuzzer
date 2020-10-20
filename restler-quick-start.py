# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import argparse
import contextlib
import os
import subprocess
from pathlib import Path

RESTLER_TEMP_DIR = Path(Path.home()).joinpath('restler_working_dir')

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

    @return: The path of the Compile directory
    @rtype : Path

    """
    if not os.path.exists(RESTLER_TEMP_DIR):
        os.makedirs(RESTLER_TEMP_DIR)

    with usedir(RESTLER_TEMP_DIR):
        subprocess.run(f'dotnet {restler_dll_path} compile --api_spec {api_spec_path}', shell=True)

    return Path(f'{RESTLER_TEMP_DIR}/Compile')

def test_spec(ip, port, use_ssl, compile_dir, restler_dll_path):
    """ Runs RESTler's test mode on a specified Compile directory

    @param ip: The IP of the service to test
    @type  ip: Str
    @param port: The port of the service to test
    @type  port: Str
    @param use_ssl: If False, set the --no_ssl parameter when executing RESTler
    @type  use_ssl: Boolean
    @param compile_dir: The Compile directory that contains the files to Test
    @type  compile_dir: Str
    @param restler_dll_path: The absolute path to the RESTler driver's dll
    @type  restler_dll_path: Str

    @return: None
    @rtype : None

    """
    command = (
        f"dotnet {restler_dll_path} test --grammar_file {compile_dir.joinpath('grammar.py')} --dictionary_file {compile_dir.joinpath('dict.json')}"
        f" --settings {compile_dir.joinpath('engine_settings.json')} --target_ip {ip} --target_port {port}"
    )
    if not use_ssl:
        command = f"{command} --no_ssl"

    with usedir(RESTLER_TEMP_DIR):
        subprocess.run(command, shell=True)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--api_spec_path',
                        help='The API Swagger specification to compile and test',
                        type=str, required=True)
    parser.add_argument('--ip',
                        help='The IP of the service to test',
                        type=str, required=True)
    parser.add_argument('--port',
                        help='The port of the service to test',
                        type=str, required=True)
    parser.add_argument('--restler_drop_dir',
                        help="The path to the RESTler drop",
                        type=str, required=True)
    parser.add_argument('--use_ssl',
                        help='Set this flag if you want to use SSL validation for the socket',
                        action='store_true')

    args = parser.parse_args()

    api_spec_path = os.path.abspath(args.api_spec_path)
    restler_dll_path = Path(os.path.abspath(args.restler_drop_dir)).joinpath('restler', 'Restler.dll')
    compile_dir = compile_spec(api_spec_path, restler_dll_path.absolute())
    test_spec(args.ip, args.port, args.use_ssl, compile_dir, restler_dll_path.absolute())

    print(f"Test complete.\nSee {RESTLER_TEMP_DIR} for results.")
