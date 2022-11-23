import time 
import sys
class RetryHandler:
    def __init__(self, type="Linear", max_retries=5, delay=5, max_delay=60):
        self.type = type
        self.max_retries = max_retries
        self.delay = delay
        self.max_delay = max_delay
        self.__num_retries = 0

    def can_retry(self):
        if self.__num_retries < self.max_retries:
            return True
        else:
            return False
    def wait_for_next_retry(self):
        if not self.can_retry():
            sys.exit(-1)

        if self.type.lower() == "linear":
            time.sleep(self.delay)
        elif self.type.lower() == "exponential":
            sleep = min(self.max_delay, self.delay * 2 ** self.__num_retries)
            time.sleep(sleep)
        self.__num_retries+=1