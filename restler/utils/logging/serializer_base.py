# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Base classes for serializing data to the trace database. """

from abc import ABC, abstractmethod

class TraceLogWriterBase(ABC):
    @abstractmethod
    def save(self, data):
        """ Save data to the trace log

        @param data: The data to be saved to the trace log
        @type  data: String

        @return: None
        @rtype : None

        """
        pass

class TraceLogReaderBase(ABC):
    @abstractmethod
    def load(self):
        """ Load data from the trace log
        @return: None
        @rtype : None
        """
        pass





