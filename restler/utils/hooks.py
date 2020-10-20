# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Useful hooks to collect coverage infromation of python services. """
from __future__ import print_function
import sys
import functools
import linecache

import pickle

# Destination of report file
REPORTDIR = os.path.abspath('/tmp/.coverage')

# Buffer that leeps the line numbers of covered (executed) statements.
DLINES = {}

def update_report(dlines):
    """ Updates file of coverage statistics.

    @param dlines: Dictionary of coverage statistics.
    @type frame: Dict

    @return: None
    @rtype: None

    """
    with open(REPORTDIR, "wb+") as f:
        # print(dlines)
        pickle.dump(dlines, f, protocol=pickle.HIGHEST_PROTOCOL)


def trace_lines(frame, event, arg):
    """ Stack unwinding callback hook to inspects lines within a function call.

    @param frame:  The frame object currently inspected (for more
        documentation of frame attributes, such as f_code, f_lineno, etc.,
        see https://docs.python.org/2/library/inspect.html)
    @type frame: Python frame object.
    @param event: Specifies the intercpeted event, such as "call", "line",
        "return", etc. (For more documentation see:
         https://docs.python.org/2/library/sys.html#sys.settrace)
    @type event: Str
    @param arg: settrace expect this argument
    @type arg: kwarg

    @return: None
    @rtype: None

    """
    if event != 'line':
        return
    co = frame.f_code
    func_name = co.co_name
    func_filename = co.co_filename
    if func_filename not in DLINES:
        DLINES[func_filename] = []

    line_no = frame.f_lineno
    if line_no not in DLINES[func_filename]:
        DLINES[func_filename].append(line_no)
        update_report(DLINES)


def trace_calls(frame, event, arg, to_be_traced=[]):
    """ Stack unwinding callback hook to inspects stack frames using settrace.

    Inspect the current frame and unwind function call events. If the function
    call originates from a file within a target group trace the funtion lines
    executed.

    @param frame:  The frame object currently inspected (for more
        documentation of frame attributes, such as f_code, f_lineno, etc.,
        see https://docs.python.org/2/library/inspect.html)
    @type frame: Python frame object.
    @param event: Specifies the intercpeted event, such as "call", "line",
        "return", etc. (For more documentation see:
         https://docs.python.org/2/library/sys.html#sys.settrace)
    @type event: Str
    @param arg: settrace expect this argument
    @type arg: kwarg
    @param to_be_traced: List of files to be traced
    @type to_be_traced: List

    @return: Traced lines.
    @rtype: @callback trace_lines

    """
    if event != 'call':
        return
    co = frame.f_code
    func_name = co.co_name
    if func_name == 'write':
        # Ignore write() calls from printing
        return
    line_no = frame.f_lineno
    filename = co.co_filename
    if not filename.endswith(to_be_traced):
        return
    # print('* Call to {} on line {} of {}'.format(
    #       func_name, line_no, filename))
    # Trace into this function
    return trace_lines
