# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import time

from enum import Enum
class RetryStrategy(Enum):
    """ Enum of retry strategies """
    LINEAR = 0
    EXPONENTIAL = 1

class RetryLimitExceeded(Exception):
    pass


class RetryHandler:
    """ Utilities for handling retries """
    def __init__(self, strategy=RetryStrategy.LINEAR, max_retries=5, delay=5, max_delay=60):
        if isinstance(strategy, RetryStrategy):
            self.strategy = strategy
        else:
            raise ValueError(f"Unknown retry strategy: {strategy}")
        self.max_retries = max_retries
        self.delay = delay
        self.max_delay = max_delay
        self.__num_retries = 0



    def can_retry(self):
        """ Determine if a retry should be executed
        @return: Whether or not a retry should be executed
        @rtype : Bool
        """
        if self.__num_retries < self.max_retries:
            return True
        else:
            return False

    def wait_for_next_retry(self):
        """ Sleep until next retry should be attempted
        @return: None
        @rtype : None
        """
        if not self.can_retry():
            raise RetryLimitExceeded("Retry limit exceeded")

        if self.strategy == RetryStrategy.LINEAR:
            time.sleep(self.delay)
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            sleep = min(self.max_delay, self.delay * 2 ** self.__num_retries)
            time.sleep(sleep)
        else:
            raise ValueError(f"Unknown retry strategy: {self.strategy}")
        self.__num_retries += 1
