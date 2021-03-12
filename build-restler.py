# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import argparse
import os
import shutil
import sys
import subprocess
import contextlib
from pathlib import Path

class Dirs:
    """ Global directories """
    def __init__(self, dest_dir, repository_root_dir, python_path):
        self.dest_dir = Path(dest_dir)
        self.engine_dest_dir = self.dest_dir.joinpath('engine')
        self.engine_build_dir = self.dest_dir.joinpath('build')
        self.repository_root_dir = Path(repository_root_dir)
        self.python_path = python_path

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

def _copy_py_files(src_root_dir, root_sub_dir, dest_dir):
    """ Helper function that copies all .py files from one directory to
    another while maintaining the directory structure.

    @param src_root_dir: The root portion of the source directory. This portion
            will be filtered out of the destination directory when
            creating the new directory tree.
    @type  src_root_dir: Path or str
    @param root_sub_dir: The subdirectory of the root where we will begin copying from.
    @type  root_sub_dir: Path or str
    @param dest_dir: The destination directory
    @type  dest_dir: Path or str

    Example:
      src_root_dir = /home/rest.fuzzing/restler/; root_sub_dir = engine; dest_dir = /home/drop/
      Recursively copies all .py files from /home/rest.fuzzing/restler/engine/*
      to /home/drop/engine/...

    """
    restler_dir = Path(f'{src_root_dir}/{root_sub_dir}')
    for dirpath, dirs, files in os.walk(restler_dir):
        for file in files:
            if file.endswith('.py'):
                # Combines the current file's directory with the destination directory after
                # removing the @src_root_dir portion of the current file's directory.
                # Example:
                #   src_root_dir=/home/rest.fuzzing/restler/; dirpath=/home/rest.fuzzing/restler/engine/core/;
                #   dest_dir=/home/drop/; dest_path=/home/drop/engine/core
                dest_path = Path(dest_dir).joinpath(*Path(dirpath).parts[len(src_root_dir.parts):])
                if not os.path.exists(dest_path):
                    os.makedirs(dest_path)
                shutil.copy(Path(f'{dirpath}/{file}'), dest_path.joinpath(file))

def copy_python_files(repo_root, dest_dir):
    """ Copies python files from repository to destination directory

    @param repo_root: The repository root
    @type  repo_root: Path or str
    @param dest_dir: The destination directory
    @type  dest_dir: Path or str

    """
    print("Copying all python files...")
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    restler = Path(f'{repo_root}/restler')
    for file in restler.glob('*.py'):
       shutil.copy(file, dest_dir)

    _copy_py_files(restler, 'engine', dest_dir)
    _copy_py_files(restler, 'checkers', dest_dir)
    _copy_py_files(restler, 'utils', dest_dir)

def get_compilation_errors(stdout):
    """ Helper that extracts compilation errors from the build's stdout """
    Error_Start = '***'
    Error_End = '\\r\\n\\r\\n'
    stdout_index = stdout.find(Error_Start)
    errors = []
    while stdout_index >= 0:
        # Partition stdout to extract the error from between Error_Start and Error_End
        parts = stdout[stdout_index + len(Error_Start):].partition(Error_End)
        # Add this error to the error list
        errors.append(parts[0])
        # Search for more errors in the rest of stdout that is beyond the previous error
        parts_index = parts[2].find(Error_Start)
        if parts_index > 0:
            # Increment the index in stdout by adding the error partitions that were already used
            stdout_index += parts_index+len(parts[0]) + len(parts[1])
        else:
            break
    return errors

def publish_engine_py(dirs):
    """ Publish the Python RESTler engine as .py files.

    Will also do a quick compilation of the files to verify that no exception occurs

    """
    # Copy files to a build directory to test for basic compilation failure
    print("Testing compilation of Python files...")
    try:
        copy_python_files(dirs.repository_root_dir, dirs.engine_build_dir)

        output = subprocess.run(f'{dirs.python_path} -m compileall {dirs.engine_build_dir}', shell=True, capture_output=True)
        if output.stderr:
            print("Build failed!")
            print(output.stderr)
            sys.exit(-1)

        stdout = str(output.stdout)
        errors = get_compilation_errors(stdout)
        if errors:
            for err in errors:
                print("\nError found!\n")
                print(err.replace('\\r\\n', '\r\n'))
            print("Build failed!")
            sys.exit(-1)

    finally:
        print("Removing compilation build directory...")
        shutil.rmtree(dirs.engine_build_dir)

    # Copy files to drop
    copy_python_files(dirs.repository_root_dir, dirs.engine_dest_dir)

def publish_dotnet_apps(dirs, configuration):
    """ Publishes the dotnet components (compiler, driver, and results analyzer)

    @param dirs: The global directories
    @type  dirs: Dirs
    @param configuration: The build configuration
    @type  configuration: Str

    """
    print("Publishing dotnet core apps...")
    dotnetcore_projects = {
        "compiler": os.path.join(f'{dirs.repository_root_dir}','src','compiler','Restler.CompilerExe','Restler.CompilerExe.fsproj'),
        "resultsAnalyzer": os.path.join(f'{dirs.repository_root_dir}','src','ResultsAnalyzer','ResultsAnalyzer.fsproj'),
        "restler": os.path.join(f'{dirs.repository_root_dir}','src','driver','Restler.Driver.fsproj')
    }

    for key in dotnetcore_projects.keys():
        target_dir_name = key
        proj_output_dir = os.path.join(f'{dirs.dest_dir}', f'{target_dir_name}')
        proj_file_path = dotnetcore_projects[target_dir_name]
        print(f"Publishing project {proj_file_path} to output dir {proj_output_dir}")

        output = subprocess.run(f"dotnet restore \"{proj_file_path}\" --use-lock-file --locked-mode --force", shell=True, stderr=subprocess.PIPE)
        if output.stderr:
            print("Build failed!")
            print(str(output.stderr))
            sys.exit(-1)
        output = subprocess.run(f"dotnet publish \"{proj_file_path}\" --no-restore -o \"{proj_output_dir}\" -c {configuration} -f netcoreapp5.0", shell=True, stderr=subprocess.PIPE)
        if output.stderr:
            print("Build failed!")
            print(str(output.stderr))
            sys.exit(-1)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--repository_root_dir',
                        help='The root of the rest.fuzzing repository.'
                        'If not specified, the root will be inferred from the location of this script in this repository.',
                        type=str, default=os.path.dirname(os.path.realpath(__file__)))
    parser.add_argument('--dest_dir',
                        help='The destination directory for the drop.',
                        type=str, required=True)
    parser.add_argument('--configuration',
                        help='The build configuration',
                        type=str, default='release', required=False)
    parser.add_argument('--python_path',
                        help='The path or python command to use for compilation. (Default: python)',
                        type=str, default='python', required=False)
    parser.add_argument('--compile_type',
                        help='all: driver/compiler & engine as python files\n'
                        'engine: engine only, as python files\n'
                        'compiler: compiler only\n'
                        '(Default: all)',
                        type=str, default='all', required=False)

    args = parser.parse_args()

    if not os.path.exists(args.dest_dir):
        os.makedirs(args.dest_dir)

    dirs = Dirs(args.dest_dir, args.repository_root_dir, args.python_path)

    print("Generating a new RESTler binary drop...")
    if args.compile_type == 'all':
        publish_dotnet_apps(dirs, args.configuration)
        publish_engine_py(dirs)
    elif args.compile_type == 'compiler':
        publish_dotnet_apps(dirs, args.configuration)
    elif args.compile_type == 'engine':
        publish_engine_py(dirs)
    else:
        print(f"Invalid compileType specified: {args.compile_type!s}")
