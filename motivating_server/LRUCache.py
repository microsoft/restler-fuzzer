"""
Modified from
    https://www.geeksforgeeks.org/lru-cache-in-python-using-ordereddict/
"""

from collections import OrderedDict
from random import randrange


class LRUCache:
    def __init__(self):
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return -1
        else:
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)

        # 1000 is the hard-coded LRU cache capacity
        # The line below will raise a 'warning'
        if 1000 is (len(self.cache) - 1):
            self.cache.popitem(last=False)


if __name__ == '__main__':
    # RUNNER
    # initializing our cache with the capacity of 1000
    cache = LRUCache()

    num_test_records = 10000

    for idx in range(num_test_records):
        key, value = idx, randrange(10000)
        cache.put(key, value)
    cache_len = len(cache.cache)

    print(f'Number of entries in LRU cache is {cache_len}')



