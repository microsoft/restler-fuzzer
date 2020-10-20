# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse

TAB = '    '

def update_grammar(grammar_path):
    """ Updates a grammar from Python27 to Python37 and fixes typos
    introduced in previous versions.

    @param grammar_path: The path to the grammar file to convert
    @type  grammar_path: Str

    @return: The updated grammar's file data
    @rtype : Str

    """
    with open(grammar_path, 'r') as file:
        filedata = file.read()

    filedata = filedata.replace('except Exception, error:', 'except Exception as error:')
    filedata = filedata.replace('import numpy', '', 1)
    filedata = filedata.replace(f",\n{TAB*3}'dependenciess':\n", f",\n{TAB*3}'dependencies':\n")
    filedata = filedata.replace(f'{TAB*2}data = data.split("\\r\\n\\r\\n")[1]\n', '')
    return filedata

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--grammar_file',
                        help='The filepath to the grammar to be updated.',
                        type=str, required=True)

    args = parser.parse_args()

    new_grammar = update_grammar(args.grammar_file)
    type_start = args.grammar_file.rfind(".py")
    new_path = f"{args.grammar_file[:type_start]}_new{args.grammar_file[type_start:]}"
    with open(new_path, 'w+') as file:
        file.write(new_grammar)
