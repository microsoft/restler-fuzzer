import typing
import random
import time
import string
import itertools
random_seed=0
print(f"Value generator random seed: {random_seed}")
random.seed(random_seed)

EXAMPLE_ARG = "examples"

# No count limit
def gen_restler_fuzzable_string(**kwargs):
    example_values=None
    if EXAMPLE_ARG in kwargs:
        example_values = kwargs[EXAMPLE_ARG]

    if example_values:
        for exv in example_values:
            yield exv
        example_values = itertools.cycle(example_values)

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


def get_integers():
    values = range(0, 5)
    for k in values:
        yield k

# Returns 5 values
def gen_restler_fuzzable_int(**kwargs):
    example_value=None
    if EXAMPLE_ARG in kwargs:
        example_value = kwargs[EXAMPLE_ARG]

    return get_integers()

# Returns 3 values
def gen_type(**kwargs):

    yield "int"
    yield "number"
    yield "string"

value_generators = {
	"restler_fuzzable_string": gen_restler_fuzzable_string,
	"restler_fuzzable_string_unquoted": None,
	"restler_fuzzable_datetime": None,
	"restler_fuzzable_datetime_unquoted": None,
	"restler_fuzzable_date": None,
	"restler_fuzzable_date_unquoted": None,
	"restler_fuzzable_uuid4": None,
	"restler_fuzzable_uuid4_unquoted": None,
	"restler_fuzzable_int":  gen_restler_fuzzable_int,
	"restler_custom_payload": {
		"type": gen_type,
	},
}
