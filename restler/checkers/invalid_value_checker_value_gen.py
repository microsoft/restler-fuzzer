import typing
import random
import time
import string
import itertools
from datetime import datetime

random_seed=time.time()
print(f"Value generator random seed: {random_seed}")
random.seed(random_seed)

EXAMPLE_ARG = "examples"


def gen_restler_fuzzable_string(**kwargs):
    example_values=None
    if EXAMPLE_ARG in kwargs:
        example_values = kwargs[EXAMPLE_ARG]

    if example_values is not None and len(example_values) > 1:
        example_values = itertools.cycle(example_values)
    else:
        example_values = None
    i = 0
    while True:
        i = i + 1
        size = random.randint(i, i + 10)
        if example_values:
            ex = next(example_values)
            ex_k = random.randint(1, len(ex) - 1)
            new_values=''.join(random.choices(ex, k=ex_k))
            yield ex[:ex_k] + new_values + ex[ex_k:]

        yield ''.join(random.choices(string.ascii_letters + string.digits, k=size))
        yield ''.join(random.choices(string.printable, k=size)).replace("\r\n", "")

def placeholder_value_generator():
    while True:
        yield str(random.randint(-10, 10))
        yield ''.join(random.choices(string.ascii_letters + string.digits, k=1))

def gen_restler_fuzzable_string_unquoted(**kwargs):
    return gen_restler_fuzzable_string(kwargs)

def gen_restler_fuzzable_datetime(**kwargs):
    example_value=None
    if EXAMPLE_ARG in kwargs:
        example_value = kwargs[EXAMPLE_ARG]

    # Add logic here to generate values
    return placeholder_value_generator()


def gen_restler_fuzzable_datetime_unquoted(**kwargs):
    return gen_restler_fuzzable_datetime(kwargs)


def gen_restler_fuzzable_date(**kwargs):
    example_value=None
    if EXAMPLE_ARG in kwargs:
        example_value = kwargs[EXAMPLE_ARG]

    # Add logic here to generate values
    return placeholder_value_generator()

    
def gen_restler_fuzzable_date_unquoted(**kwargs):
    return gen_restler_fuzzable_date(kwargs)


def gen_restler_fuzzable_int(**kwargs):
    example_value=None
    if EXAMPLE_ARG in kwargs:
        example_value = kwargs[EXAMPLE_ARG]

    # Add logic here to generate values
    return placeholder_value_generator()


value_generators = {
	"restler_fuzzable_string": gen_restler_fuzzable_string,
	"restler_fuzzable_string_unquoted": None,
	"restler_fuzzable_datetime": None,
	"restler_fuzzable_datetime_unquoted": None,
	"restler_fuzzable_date": None,
	"restler_fuzzable_date_unquoted": None,
	"restler_fuzzable_uuid4": None,
	"restler_fuzzable_uuid4_unquoted": None,
	"restler_fuzzable_int": None
}
