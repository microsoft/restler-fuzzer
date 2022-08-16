import typing
from random import Random
import time
import string
import itertools
from datetime import datetime
import sys

random_seed=time.time()
global random_gen
random_gen = Random(random_seed)
print(f"Invalid value generator random seed: {random_seed}")

def set_random_seed(seed):
    print(f"Setting invalid value generator random seed: {seed}")
    global random_gen
    random_gen = Random(seed)

EXAMPLE_ARG = "examples"

def get_boundary_values():
    yield ''.join(random_gen.choices(string.ascii_letters + string.digits, k=10000))
    yield ''.join(random_gen.choices(string.digits, k=10000))
    yield ''
    yield '{}'
    yield '[]'


def gen_restler_fuzzable_string(**kwargs):
    for bv in get_boundary_values():
        yield bv

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
        size = random_gen.randint(i, i + 10)
        if example_values:
            ex = next(example_values)
            ex_k = random_gen.randint(1, len(ex) - 1)
            new_values=''.join(random_gen.choices(ex, k=ex_k))
            yield ex[:ex_k] + new_values + ex[ex_k:]

        yield ''.join(random_gen.choices(string.ascii_letters + string.digits, k=size))
        yield ''.join(random_gen.choices(string.printable, k=size)).replace("\r\n", "")

def placeholder_value_generator():
    for bv in get_boundary_values():
        yield bv
    while True:
        yield str(random_gen.randint(-10, 10))
        yield ''.join(random_gen.choices(string.ascii_letters + string.digits, k=1))
        yield ''.join(random_gen.choices(string.ascii_letters + string.digits, k=5))
        yield str(random_gen.uniform(-10000, 10000))
        yield ''.join(random_gen.choices(string.digits, k=random_gen.randint(1, 20)))


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

def gen_restler_fuzzable_object(**kwargs):
    example_value=None
    if EXAMPLE_ARG in kwargs:
        example_value = kwargs[EXAMPLE_ARG]

    # Add logic here to generate values
    return placeholder_value_generator()

def gen_restler_fuzzable_number(**kwargs):
    example_value=None
    if EXAMPLE_ARG in kwargs:
        example_value = kwargs[EXAMPLE_ARG]

    # Add logic here to generate values
    return placeholder_value_generator()

value_generators = {
	"restler_fuzzable_string": gen_restler_fuzzable_string,
	"restler_fuzzable_string_unquoted": gen_restler_fuzzable_string,
	"restler_fuzzable_datetime": gen_restler_fuzzable_datetime,
	"restler_fuzzable_number": gen_restler_fuzzable_number,
	"restler_fuzzable_datetime_unquoted": gen_restler_fuzzable_datetime,
	"restler_fuzzable_date": gen_restler_fuzzable_date,
	"restler_fuzzable_date_unquoted": gen_restler_fuzzable_date,
	"restler_fuzzable_object": gen_restler_fuzzable_object,
    "restler_fuzzable_uuid4": None,
	"restler_fuzzable_uuid4_unquoted": None,
	"restler_fuzzable_int": gen_restler_fuzzable_int,
}
