# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import print_function

import os
import threading

import utils.logger as logger

class CheckerLog(object):
    def __init__(self, checker_name):
        """ Creates a log file of a specified name

        @param checker_name: The name of the checker that this log is for
        @type  checker_name: Str

        """
        self._checker_name = checker_name
        thread_id = threading.current_thread().ident
        self._log_path = os.path.join(logger.LOGS_DIR, f'{self._checker_name}.{thread_id!s}.txt')
        if not os.path.exists(self._log_path):
            try:
                os.makedirs(os.path.dirname(self._log_path))
            except OSError:
                return None

    def checker_print(self, msg, print_to_network_log=True):
        """ Prints message to the checker log file

        @param msg: The message to print.
        @type  msg: Str

        """
        msg = logger.remove_tokens_from_logs(msg)
        with open(self._log_path, "a+") as log_file:
            print(msg, file=log_file)
        if print_to_network_log:
            logger.raw_network_logging(self._checker_name + ' ' + msg)
