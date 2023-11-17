# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import engine.core.requests as requests
import engine.core.sequences as sequences
import time
import engine.core.status_codes_monitor as status_codes_monitor

from engine.core.requests import GrammarRequestCollection
from restler_settings import Settings
import utils.logger as logger
from utils.logging.trace_db import SequenceTracker
import utils.formatting as formatting
from engine.errors import TransportLayerException
from engine.transport_layer import messaging as messaging
from engine.core.fuzzing_monitor import Monitor

def delete_create_once_resources(destructors, fuzzing_requests):
    """ Iterates through each destructor request and sends it to the server

    @param destructors: A list of destructor requests to send
    @type  destructors: list(Request)
    @param fuzzing_requests: The global collection of requests to fuzz
    @type  fuzzing_requests: FuzzingRequestCollection

    @return: None
    @rtype : None

    """
    if not destructors:
        return

    candidate_values_pool = GrammarRequestCollection().candidate_values_pool

    logger.write_to_main("\nRendering for create-once resource destructors:\n")
    SequenceTracker.set_origin('preprocessing')

    for destructor in destructors:
        status_codes = []
        try:
            logger.write_to_main(f"{formatting.timestamp()}: Endpoint - {destructor.endpoint_no_dynamic_objects}")
            logger.write_to_main(f"{formatting.timestamp()}: Hex Def - {destructor.method_endpoint_hex_definition}")
            seq = sequences.Sequence([destructor])
            renderings = seq.render(GrammarRequestCollection().candidate_values_pool,
                                            None,
                                            postprocessing=True)
            if not renderings.valid:
                logger.write_to_main(f"{formatting.timestamp()}: Rendering INVALID")
            else:
                logger.write_to_main(f"{formatting.timestamp()}: Rendering VALID")
            logger.format_rendering_stats_definition(
                destructor, GrammarRequestCollection().candidate_values_pool
            )
            if Settings().in_smoke_test_mode():
                if renderings.sequence:
                    renderings.sequence.last_request.stats.request_order = 'Postprocessing'
                    renderings.sequence.last_request.stats.set_all_stats(renderings)
                    logger.print_request_coverage(rendered_sequence=renderings, log_rendered_hash=True)

        except Exception as error:
            msg = f"Failed to delete create_once resource: {error!s}"
            logger.raw_network_logging(msg)
            logger.write_to_main(msg, print_to_console=True)
            if Settings().in_smoke_test_mode():
                if renderings.sequence:
                    renderings.sequence.last_request.stats.request_order = 'Postprocessing'
                    renderings.sequence.last_request.stats.set_all_stats(renderings)
                    logger.print_request_coverage(rendered_sequence=renderings, log_rendered_hash=True)

            pass

    Monitor().current_fuzzing_generation += 1

    logger.print_request_rendering_stats(
        candidate_values_pool,
        fuzzing_requests,
        Monitor(),
        fuzzing_requests.size_all_requests,
        logger.POSTPROCESSING_GENERATION,
        None
    )
    SequenceTracker.clear_origin()
