# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Defines exception for customized error handling. """


class TransportLayerException(Exception):
    """ Handles transport layer exceptions. """
    def __init__(self, value):
        """ Initializes error object for transport layer exception.

        @param value: The error string.
        @type  value: Str

        @return: None
        @rtype : None

        """
        self.parameter = value

    def __str__(self):
        """ Return printable object.

        @return: Error message.
        @rtype : Str

        """
        return repr(self.parameter)


class ResponseParsingException(Exception):
    def __init__(self, value):
        """ Initializes error object for parsing exception.

        @param value: The error string.
        @type  value: Str

        @return: None
        """
        self.parameter = value

    def __str__(self):
        """ Return printable object.

        @return: Error message.
        @rtype : Str

        """
        return repr(self.parameter)


class TimeOutException(Exception):
    def __init__(self, value):
        """ Initializes error object for timeout exception.

        @param value: The error string.
        @type  value: Str

        @return: None
        @rtype : None

        """
        self.parameter = value

    def __str__(self):
        """ Return printable object.

        @return: Error message.
        @rtype : Str

        """
        return repr(self.parameter)


class ExhaustSeqCollectionException(Exception):
    def __init__(self, value):
        """ Initializes error object when running out or renderings.

        @param value: The error string.
        @type  value: Str

        @return: None
        @rtype : None

        """
        self.parameter = value

    def __str__(self):
        """ Return printable object.

        @return: Error message.
        @rtype : Str

        """
        return repr(self.parameter)


class InvalidDictionaryException(Exception):
    """ To be raised when an invalid fuzzing dictionary is identified.
    """
    pass

class NoTokenSpecifiedException(Exception):
    """ To be raised when a token was expected in a request,
    but no token was found when querying for get_token
    """
    pass
