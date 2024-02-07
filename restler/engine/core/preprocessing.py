# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import print_function
import re
import json

import engine.core.driver as driver
import engine.core.fuzzing_requests as fuzzing_requests

import utils.logger as logger
from utils.logging.trace_db import SequenceTracker
import utils.formatting as formatting
import engine.dependencies as dependencies
import engine.core.sequences as sequences
from engine.fuzzing_parameters.request_examples import *
from engine.fuzzing_parameters.body_schema import *
from engine.fuzzing_parameters.parameter_schema import *
from engine.core.requests import GrammarRequestCollection
from engine.core.request_utilities import str_to_hex_def
from restler_settings import Settings
from engine.core.fuzzing_monitor import Monitor

class CreateOnceFailure(Exception):
    def __init__(self, destructors, msg):
        self.destructors = destructors
        self.msg = msg

class InvalidCreateOnce(CreateOnceFailure):
    def __init__(self, destructors):
        CreateOnceFailure.__init__(self,
            destructors,
            "A create_once endpoint was specified, but it does not exist in the grammar."
        )

class FailedToCreateResource(CreateOnceFailure):
    def __init__(self, destructors):
        CreateOnceFailure.__init__(self,
            destructors,
            "Failed to create resources for 'create_once' resource."
        )

def create_fuzzing_req_collection(path_regex):
    """ Filters the request collection to create the fuzzing
    request collection.

    @param path_regex: The regex string used for filtering
    @type  path_regex: Str

    @return: The fuzzing request collection
    @rtype : FuzzingRequestCollection

    """
    fuzz_reqs = fuzzing_requests.FuzzingRequestCollection()
    included_requests= set()
    included_all_reqs = True
    for request in GrammarRequestCollection():
        include_req = Settings().include_request(request.endpoint_no_dynamic_objects, request.method)
        if include_req and path_regex:
            include_req = re.findall(path_regex, request.endpoint_no_dynamic_objects)
        if include_req:
            reqs = driver.compute_request_goal_seq(
                request, GrammarRequestCollection())
            for req in reqs:
                if req not in included_requests:
                    included_requests.add(req)
        else:
            included_all_reqs = False
    if included_all_reqs:
        # TODO: For ordering backwards compatibility - once test baselines are updated,
        # this should be removed.
        included_requests = list (GrammarRequestCollection()._requests)
    else:
        included_requests = list (included_requests)

    # Sort the request list by hex definition so the requests are
    # always traversed in the same order.
    # TODO: GitHub #233 The requests should be sorted in all test modes
    # this requires updating test baselines, which should be done after #233 is merged.
    if Settings().in_smoke_test_mode():
        included_requests.sort(key=lambda x : x.method_endpoint_hex_definition)
    fuzz_reqs.set_all_requests(included_requests)

    return fuzz_reqs


def _set_method_endpoint_schemas(examples: RequestExamples, body_schema: BodySchema, query_schema: QueryList,
                 headers_schema: HeaderList, method: str, endpoint: str,
                 req_collection=None):
    """ Assigns a specified RequestExamples object to the matching
    request in the RequestCollection

    @param examples: The RequestExamples object to set
    @param body_schema: The BodySchema object to set
    @param method: The request's method
    @param endpoint: The request's endpoint
    @param req_collection: The request collection to which the json schema corresponds.
                           If None, use the global request collection.
    @type  req_collection: RequestCollection

    @return: None

    """
    def _print_req_not_found():
        logger.write_to_main(
            "Request from grammar does not exist in the Request Collection!\n"
            f"{method} {endpoint}\n",
            print_to_console=True
        )

    request_collection = GrammarRequestCollection().request_id_collection if req_collection is None else req_collection

    hex_def = str_to_hex_def(endpoint)
    # Find the request's endpoint in the request collection
    if hex_def in request_collection:
        # Find the matching request by method.
        # This loop will run max n = # unique methods for the request
        for req in request_collection[hex_def]:
            if req.method == method:
                if examples:
                    # Set the request's matching examples
                    req.set_examples(examples)
                if body_schema:
                    # Set the request's matching body schema
                    req.set_body_schema(body_schema)
                if query_schema is not None:  # TODO: need to wrap querylist so 'if query-schema' works as expected
                    # Set the request's matching query schema
                    req.set_query_schema(query_schema)
                if headers_schema is not None:  # TODO: need to wrap headerlist, see above.
                    # Set the request's matching header schema
                    req.set_headers_schema(headers_schema)
                break
        else:
            # The endpoint was found in the request collection, but not with this method
            _print_req_not_found()
    else:
        # Failed to find request in the request collection
        _print_req_not_found()

def parse_grammar_schema(schema_json, req_collection=None):
    """ Parses the grammar.json file for examples and body schemas and sets the
    examples for each matching request in the RequestCollection

    @param schema_json: The json schema to parse for examples
    @type  schema_json: Json

    @param req_collection: The request collection to which the json schema corresponds.
                           If None, use the global request collection.
    @type  req_json: RequestCollection

    @return: False if there was an exception while parsing the examples
    @rtype : Bool

    """
    try:
        # Process request schema by looping through each request in grammar.json
        for request_schema_json in schema_json['Requests']:
            method = request_schema_json['method'].upper()
            endpoint = request_schema_json['id']['endpoint']
            # Parse json using the RequestExamples class to create a collection of
            # examples for each request.
            try:
                request_examples = RequestExamples(request_schema_json)
            except NoExamplesFound:
                # No examples exist for this request
                request_examples = None

            try:
                body_schema = BodySchema(request_schema_json)
            except NoSchemaFound:
                # No body schema exists for this request
                body_schema = None

            try:
                query_schema = QueryList(request_schema_json)
            except NoQuerySchemaFound:
                # No query schema exists for this request
                # This should never happen for valid payloads.
                query_schema = None

            try:
                headers_schema = HeaderList(request_schema_json)
            except NoHeaderSchemaFound:
                # No header schema exists for this request
                # This should never happen for valid payloads.
                headers_schema = None

            if request_examples or body_schema or \
                (headers_schema is not None) or (query_schema is not None):
                _set_method_endpoint_schemas(request_examples, body_schema, query_schema, headers_schema, method,
                                             endpoint, req_collection=req_collection)

        return True
    except ValueError as err:
        logger.write_to_main(f"Failed to parse grammar file for examples: {err!s}", print_to_console=True)
        return False

def apply_create_once_resources(fuzzing_requests):
    """ Attempts to create all of the resources in the 'create_once' endpoints.

    @param fuzzing_requests: The collection of requests to be fuzzed
    @type  fuzzing_requests: FuzzingRequestCollection

    @return: A list of destructors to use to cleanup the create_once resources
    @rtype : list(Request)

    """
    def exclude_requests(pre_reqs, post_reqs):
        # Exclude any requests that produce or destroy the create_once endpoint
        for req_i in pre_reqs:
            fuzzing_requests.exclude_preprocessing_request(req_i)
        for req_i in post_reqs:
            fuzzing_requests.exclude_postprocessing_request(req_i)

    create_once_endpoints = Settings().create_once_endpoints

    if not create_once_endpoints:
        return

    logger.create_network_log(logger.LOG_TYPE_PREPROCESSING)
    SequenceTracker.set_origin('preprocessing')

    destructors = set()
    exclude_reqs = set()
    request_count = 0

    logger.write_to_main("Rendering for create-once resources:\n")
    # Iterate through each 'create_once' endpoint
    for endpoint in create_once_endpoints:
        # Verify that the endpoint exists in the request collection
        if endpoint in GrammarRequestCollection().request_id_collection:
            # The create_once resource generator
            resource_gen_req = None
            # Iterate through each of the requests that contain the create_once endpoint
            for req in GrammarRequestCollection().request_id_collection[endpoint]:
                if req not in fuzzing_requests:
                    logger.write_to_main(
                        "Warning: Create-once endpoint is not a request in the fuzzing list\n",
                        True)
                    break
                if not resource_gen_req and req.is_resource_generator():
                    resource_gen_req = req
                    # Compute the sequence necessary to create the create_once resource
                    req_list = driver.compute_request_goal_seq(
                        resource_gen_req, fuzzing_requests)
                    logger.write_to_main(f"{formatting.timestamp()}: Endpoint - {resource_gen_req.endpoint_no_dynamic_objects}")
                    logger.write_to_main(f"{formatting.timestamp()}: Hex Def - {resource_gen_req.method_endpoint_hex_definition}")
                    create_once_seq = sequences.Sequence(req_list)
                    renderings = create_once_seq.render(GrammarRequestCollection().candidate_values_pool,
                                            None,
                                            preprocessing=True)

                    if Settings().in_smoke_test_mode():
                        if renderings.sequence:
                            renderings.sequence.last_request.stats.request_order = 'Preprocessing'
                            renderings.sequence.last_request.stats.set_all_stats(renderings)
                            logger.print_request_coverage(rendered_sequence=renderings, log_rendered_hash=True)

                    # Make sure we were able to successfully create the create_once resource
                    if not renderings.valid:
                        logger.write_to_main(f"{formatting.timestamp()}: Rendering INVALID")
                        exclude_requests(exclude_reqs, destructors)
                        raise FailedToCreateResource(destructors)

                    logger.write_to_main(f"{formatting.timestamp()}: Rendering VALID")
                    logger.format_rendering_stats_definition(
                        resource_gen_req, GrammarRequestCollection().candidate_values_pool
                    )

                if req.is_destructor():
                    # Add destructors to the destructor list that will be returned
                    destructors.add(req)

            # Only continue processing if a resource generator was actually found for this endpoint
            if not resource_gen_req:
                continue
            request_count += len(req_list)
            # Get the set of all dynamic object names in the endpoint
            var_names = resource_gen_req.consumes.union(resource_gen_req.produces)
            # This dictionary will map dynamic object names to the values created during
            # this preprocessing create-once step.
            dynamic_object_values = {}
            for name in var_names:
                dynamic_object_values[name] = dependencies.get_variable(name)

            # Iterate through the entire request collection, searching for requests that include
            # the create_once resource. We want to "lock" the resources in these requests with
            # the dynamic object values that were created during this preprocessing step.
            for req_i in fuzzing_requests:
                # Set the variables in any requests whose consumers were produced
                # by the create_once resource generator
                if resource_gen_req.produces & req_i.consumes:
                    req_i.set_id_values_for_create_once_dynamic_objects(dynamic_object_values, renderings)
                # Exclude any requests that produce the create_once object(s)
                if resource_gen_req.produces & req_i.produces:
                    exclude_reqs.add(req_i)
        else:
            exclude_requests(exclude_reqs, destructors)
            raise InvalidCreateOnce(destructors)

    exclude_requests(exclude_reqs, destructors)

    # Reset all of the dynamic object values that were just created
    dependencies.reset_tlb()
    # Reset the garbage collector, so it doesn't delete any of the resources that were just created
    dependencies.set_saved_dynamic_objects()

    logger.print_request_rendering_stats(
        GrammarRequestCollection().candidate_values_pool,
        fuzzing_requests,
        Monitor(),
        request_count,
        logger.PREPROCESSING_GENERATION,
        None
    )
    SequenceTracker.clear_origin()

    # Return the list of destructors that were removed from the request collection.
    # These will be used to cleanup the create_once resources created during preprocessing.
    return list(destructors)
