# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
import time
from engine.core.retry_handler import RetryHandler, RetryStrategy, RetryLimitExceeded

class RetryHandlerTest(unittest.TestCase):

    def test_invalid_strategy(self):
        """ Test that an invalid strategy raises an exception """
        with self.assertRaises(ValueError):
            RetryHandler(strategy="invalid")

    def test_linear_retries(self):
        """ Test that linear retries work as expected
            Should take about 10 seconds (5 retries * 2 second delay)
            RetryLimitExceeded should be raised on the 6th retry"""
        retry_handler = RetryHandler(RetryStrategy.LINEAR, max_retries=5, delay=2)
        start = time.time()
        for i in range(5):
            self.assertTrue(retry_handler.can_retry())
            retry_handler.wait_for_next_retry()
        self.assertFalse(retry_handler.can_retry())
        with self.assertRaises(RetryLimitExceeded):
            retry_handler.wait_for_next_retry()
        end = time.time()
        ## Allow for a 1 second delta - this should take about 9 seconds
        self.assertAlmostEqual(end - start, 10, delta=1)

    def test_exponential_retries(self):
        """ Test that exponential retries work as expected
            Should take about 34 seconds (2 + 4 + 8 + 10 + 10)
            RetryLimitExceeded should be raised on the 6th retry"""
        retry_handler = RetryHandler(RetryStrategy.EXPONENTIAL, max_retries=5, delay=2, max_delay=10)
        start = time.time()
        for i in range(5):
            self.assertTrue(retry_handler.can_retry())
            retry_handler.wait_for_next_retry()
        self.assertFalse(retry_handler.can_retry())
        with self.assertRaises(RetryLimitExceeded):
            retry_handler.wait_for_next_retry()
        end = time.time()

        ## Allow for a 1 second delta - this should take about 34 seconds
        self.assertAlmostEqual(end - start, 34, delta=1)
