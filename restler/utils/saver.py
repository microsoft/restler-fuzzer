# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Saver module. """
import os
import pickle

import utils.logger as logger
import utils.formatting as formatting


def save(req_collection, seq_collection, fuzzing_collection, fuzzing_monitor, length):
    """ Save in checkpoint fuzzing of latest generation.

    @param req_collection: The request collection.
    @type  req_collection: RequestCollection class object.
    @param seq_collection: List of sequences in sequence collection.
    @type  seq_collection: List
    @param fuzzing_collection: The collection of requests being fuzzed
    @type  fuzzing_collection: FuzzingRequestCollection
    @param fuzzing_monitor: The global monitor for the fuzzing run
    @type  fuzzing_monitor: FuzzingMonitor
    @param length: Length of latest generation.
    @type length: Int

    @return: None
    @rtype : None

    """
    return
    if not os.path.exists(logger.CKPT_DIR):
        os.makedirs(logger.CKPT_DIR)

    current_ckpt = os.path.join(logger.CKPT_DIR, "checkpoint-{}".format(length))
    print("{}: Saving checkpoint: {}".format(formatting.timestamp(), current_ckpt))

    with open(current_ckpt, "wb") as f:
        state = {
            'req_collection': req_collection,
            'fuzzing_collection': fuzzing_collection,
            'fuzzing_monitor': fuzzing_monitor,
            'seq_collection': seq_collection,
            'length': length
        }
        pickle.dump(state, f)


def load(req_collection, seq_collection, fuzzing_collection, fuzzing_monitor):
    """ Load from checkpoint fuzzing of lattest generation.

    @param req_collection: The target request collection.
    @type  req_collection: RequestCollection class object.
    @param seq_collection: The tareg list of sequences in sequence collection.
    @type  seq_collection: List
    @param length: Length of lattest generation.
    @type length: Int

    @return: A tuple of ('length', request collection', 'sequence collection')
    @rtype : Tuple

    """
    length = 0
    print("No checkpoints used at this phase")
    return req_collection, seq_collection, fuzzing_collection, fuzzing_monitor, length
    if not os.path.exists(logger.CKPT_DIR):
        print("{}: No chekpoint found".format(formatting.timestamp()))
        return req_collection, seq_collection, fuzzing_collection, fuzzing_monitor, length
    ckpt_files = [os.path.join(logger.CKPT_DIR, f)
                  for f in os.listdir(logger.CKPT_DIR)
                  if os.path.isfile(os.path.join(logger.CKPT_DIR, f))]
    if not ckpt_files:
        print("{}: No chekpoint found".format(formatting.timestamp()))
        return req_collection, seq_collection, fuzzing_collection, fuzzing_monitor, length

    lattest_ckpt = sorted(ckpt_files)[-1]
    print("{}: Loading state from: {}".format(formatting.timestamp(),
                                              lattest_ckpt))
    with open(lattest_ckpt, "rb") as f:
        state = pickle.load(f)
    req_collection = state['req_collection']
    seq_collection = state['seq_collection']
    fuzzing_collection = state['fuzzing_collection']
    fuzzing_monitor = state['fuzzing_monitor']
    length = state['length']
    print("{}: Candidate values: {}".\
          format(formatting.timestamp(),
                 req_collection.candidate_values_pool.candidate_values))
    print("{}: Past test cases: {}".format(formatting.timestamp(),
                                           fuzzing_monitor.num_test_cases()))
    fuzzing_monitor.reset_start_time()
    return req_collection, seq_collection, fuzzing_collection, fuzzing_monitor, length
