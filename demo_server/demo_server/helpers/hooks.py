# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Simple debugger that continiously produces coverage statics on a set of target
files and writes the relevant information on persistent storage

"""
from __future__ import print_function
import sys
import functools
import linecache

import time
import pickle

# Destination of report file
REPORTDIR = 'coverage_stats.txt'

# Buffer -- Keeps line numbers of covered (executed) statmets
DLINES = {}


def update_report(dlines):
    with open(REPORTDIR, "w+") as f:
        for func_filename in dlines:
            for (line_no, time_micro) in dlines[func_filename]:
                print("{}:{}:{}".format(time_micro, func_filename, line_no),
                      file=f)
        f.close()


def trace_lines(frame, event, arg):
    ''' Stack unwinding callback hook to inspects lines within a function call.

    @frame:  frame, the frame object currently inspected (for more
        documentation of frame attributes, such as f_code, f_lineno, etc.,
        see https://docs.python.org/2/library/inspect.html)

    @event: str, specifies the intercpeted event, such as "call", "line",
        "return", etc. (For more documentation see:
         https://docs.python.org/2/library/sys.html#sys.settrace)

    @arg: kwarg, settrace expect this argument
    '''
    if event != 'line':
        return
    co = frame.f_code
    func_name = co.co_name
    func_filename = co.co_filename
    if func_filename not in DLINES:
        DLINES[func_filename] = []

    line_no = frame.f_lineno
    time_micro = int(time.time()*10**6)
    registered_lines = map(lambda x: x[0], DLINES[func_filename])
    if line_no not in registered_lines:
        DLINES[func_filename].append((line_no, time_micro))
        update_report(DLINES)


def trace_calls(frame, event, arg, to_be_traced='demo_server'):
    ''' Stack unwinding callback hook to inspects stack frames using settrace.

    Inspect the current frame and unwind function call events. If the function
    call originates from a file within a target group trace the funtion lines
    executed.

    @frame:  frame, the frame object currently inspected (for more
        documentation of frame attributes, such as f_code, f_lineno, etc.,
        see https://docs.python.org/2/library/inspect.html)

    @event: str, specifies the intercpeted event, such as "call", "line",
        "return", etc. (For more documentation see:
         https://docs.python.org/2/library/sys.html#sys.settrace)

    @arg: kwarg, settrace expect this argument

    @to_be_traced: list, keeps track of target files to report coverage on
    '''
    if event != 'call':
        return
    co = frame.f_code
    func_name = co.co_name
    if func_name == 'write':
        # Ignore write() calls from printing
        return
    line_no = frame.f_lineno
    filename = co.co_filename
    if "venv" in filename:
        return
    if to_be_traced not in filename:
        return
    # print('* Call to {} on line {} of {}'.format(
    #       func_name, line_no, filename))
    # Trace into this function
    return trace_lines

