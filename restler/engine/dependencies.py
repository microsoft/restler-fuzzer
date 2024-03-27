# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Dynamic Variabes a.k.a. dependencies and dynamic objects garbage collection.
"""
from __future__ import print_function
import time
import threading
import sys
import json
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

import utils.formatting as formatting
from utils.logging.trace_db import SequenceTracker
from restler_settings import Settings

class ResourceTypeQuotaExceededException(Exception):
    pass

threadLocal = threading.local()
# Keep TLS tlb to enforce mutual exclusion when using >1 fuzzing jobs.
threadLocal.tlb = {}
tlb = threadLocal.tlb
# The 'local_dyn_objects_cache' tracks dynamic objects that are created while
# rendering the sequence prefix and must not be deleted until the prefix is no longer in use.
threadLocal.local_dyn_objects_cache = {}
local_dyn_objects_cache = threadLocal.local_dyn_objects_cache
gc_paused = False

# Keep a global registry for garbage collection (deletion) of dynamic objects.
dyn_objects_cache = {}
dyn_objects_cache_lock = None

# Dynamic objects that must not be deleted until the end of fuzzing
saved_dyn_objects = {}

# Misc book-keeping
object_accesses = 0
object_creations = 0
RDELIM = '_READER_DELIM'

class DynamicVariable:
    """ Dynamic variable object. """
    def __init__(self, type):
        """ Initializes a  dynamic variable (a.k.a. dependency).

        @param type: The type of the dynamic variable.
        @type  type: Str

        @return: None
        @rtype : None

        """
        self._var_type = type
        self._payload_placeholder = RDELIM + type + RDELIM
        if type not in tlb:
            tlb[type] = None
            return

    def reader(self):
        """ Returns an empty placeholder tagged with the type of the dynamic
        variable. This placeholder has a specific delimiter,
        @global_param RDELIM, which is going to be parsed during processing of
        Request class objects for two purposes:

            * First, in order to determine whether and how many dependencies,
            i.e., dynamic variables, a Request definition contains and build
            the appropriateconsumer dependencies.
            (file: requests.py/ method: set_constraints())

            *  Second, during sequence rendering the dependencies of each request
            must be substituted with their actual values that have been
            dynamically obtained by parsing the responses of the appropriate
            producers. The values that need to be dynamically resolved and
            substituted are marked by this custom delimiter.

        @return: Dynamic variable's value placeholder.
        @rtype : Str

        """
        return self._payload_placeholder

    def writer(self, parser=None):
        """ Return the tag (type) of the dependency. This is useful to mark
        Request objects that are producers of some dynamic variable.

        @return: Dynamic variable's type.
        @rtype : Str

        """
        return self._var_type

def get_variable(type):
    """ Getter for dynamic variable (a.k.a. dependency).

    @param type: The type of the dynamic variable.
    @type  type: Str

    @return: The value of the variable.
    @rtype:  Str

    """
    global object_accesses
    object_accesses += 1

    if type not in tlb:
        return ''

    # Make sure the value is properly escaped for being sent
    value = tlb[type]
    if not Settings().encode_dynamic_objects:
        return value

    encoded_value = json.dumps(value)
    if isinstance(value, (str)):
        encoded_value = encoded_value[1:-1]

    # thread_id = threading.current_thread().ident
    # print("Getting: {} / Value: {} ({})".format(type, encoded_value, thread_id))
    return encoded_value

def __add_variable_to_dyn_cache(type, value, obj_cache, cache_lock):
    # Keep track of all dynamic objects ever created.
    if cache_lock is not None:
        cache_lock.acquire()
    if type not in obj_cache:
        obj_cache[type] = []
    obj_cache[type].append(value)
    if cache_lock is not None:
        cache_lock.release()

def set_variable(type, value):
    """ Setter for dynamic variable (a.k.a. dependency).

    @param type: The type of the dynamic variable.
    @type  type: Str
    @param value: The value to assign to the dynamic vairable.
    @type  type: Str

    @return: None
    @rtype : None

    """
    global object_creations
    object_creations += 1

    tlb[type] = value
    # thread_id = threading.current_thread().ident
    # print("Setting: {} / Value: {} ({})".format(type, value, thread_id))
    if gc_paused:
        __add_variable_to_dyn_cache(type, value, local_dyn_objects_cache, None)
    else:
        __add_variable_to_dyn_cache(type, value, dyn_objects_cache, dyn_objects_cache_lock)

def print_variables():
    """ Prints all dynamic variables and their values.

    @return: None
    @rtype : None

    """
    from utils.logger import raw_network_logging as RAW_LOGGING

    for k in tlb:
        RAW_LOGGING("{}: {}".format(k, tlb[k]))

def set_variable_no_gc(type, value):
    """ Setter for dynamic variable that should never be garbage collected.

    @param type: The type of dynamic variable.
    @type  type: Str
    @param value: The value to assign to the dynamic variable.
    @type  value: Str

    @return: None
    @rtype : None

    """
    tlb[type] = value

def reset_tlb():
    """ Reset internal tlb of dynamic variables.

    @return: None
    @rtype : None

    """
    for k in tlb:
        tlb[k] = None

def clear_saved_local_dyn_objects():
    """ Moves all of the saved objects from the saved objects cache to the regular tlb, so
    they can be deleted.
    """
    if gc_paused:
        raise Exception("Error: cannot clear saved dynamic objects while they are being saved.")

    if dyn_objects_cache_lock is not None:
        dyn_objects_cache_lock.acquire()
    for type in local_dyn_objects_cache:
        if type not in dyn_objects_cache:
            dyn_objects_cache[type] = []
        dyn_objects_cache[type] = dyn_objects_cache[type] + local_dyn_objects_cache[type]
    if dyn_objects_cache_lock is not None:
        dyn_objects_cache_lock.release()

    local_dyn_objects_cache.clear()


def start_saving_local_dyn_objects():
    """ Instead of adding saved dynamic objects to the regular tlb, add it to the saved tlb.
    This will save them until explicitly released.
    """
    global gc_paused
    if gc_paused:
        raise Exception("Error: the GC is already paused.")

    gc_paused = True

def stop_saving_local_dyn_objects(reset=False):
    """ Set the state so that any future objects that are created are
    added to the regular TLB and will be garbage collected automatically.

    @param reset: If 'True', also release the saved objects.
    @type reset: Bool

    @return: None
    @rtype : None
    """
    global gc_paused
    gc_paused = False
    if reset:
        clear_saved_local_dyn_objects()

def set_saved_dynamic_objects():
    """ Saves the current dynamic objects cache to a separate
    cache and then clears the dynamic objects cache. This
    function should only be called once per fuzzing run.

    @return: None
    @rtype : None

    """
    global saved_dyn_objects
    if saved_dyn_objects:
        raise Exception("Attempting to save dynamic objects for a second time.")
    saved_dyn_objects = dict(dyn_objects_cache)
    dyn_objects_cache.clear()

# These codes are used by the garbage collector to determine whether
# or not a resource can be removed from the dynamic objects cache.
# 200 and 202 codes indicate that the DELETE request was successful
# 204 and 404 indicate that the resource does not exist. This happens
# when the resource has already been deleted during the fuzzing run
DELETED_CODES = ['200', '204', '404']
DELETED_CODES_ASYNC = ['202']

class GarbageCollector:
    """ Garbage collector class
    """
    def __init__(self, req_collection, fuzzing_monitor):
        """ Uses requests from @param req_collection to garbage collect, i.e.,
        try to periodically try deleting dynamic objects.

        @param req_collection: The requests collection.
        @type  req_collection: RequestCollection class object.
        @param fuzzing_monitor: The global monitor for the fuzzing run
        @type  fuzzing_monitor: FuzzingMonitor

        @return: None
        @rtype : None

        """
        self._dyn_objects_cache_size = \
            0 if Settings().run_gc_after_every_sequence else Settings().dyn_objects_cache_size

        self.req_collection = req_collection
        self.monitor = fuzzing_monitor

        global dyn_objects_cache_lock
        dyn_objects_cache_lock = multiprocessing.Lock()
        self.dyn_objects_cache_lock = dyn_objects_cache_lock

        global dyn_objects_cache
        self.dyn_objects_cache = dyn_objects_cache

        global saved_dyn_objects
        self.saved_dyn_objects = saved_dyn_objects

        self._destructor_types = []

        # This is a buffer of all overflowing dynamic objects created during the
        # lifetime of fuzzing.
        self.overflowing = {}

        # The deletions that have not yet completed, and require polling to get the final state
        self.async_deletions = {}

        # The number of failed deletions.
        self.num_failed_deletions = 0

        # Statistics on deleted objects
        # Shows the error codes for DELETEs attempted per object type
        self.gc_stats = {}

        self._finishing = False
        self._created_network_log = False
        self._cleanup_event = threading.Event()
        self._cleanup_done_event = threading.Event()
        self._cleanup_done_event_timeout = 3600 # 1 hour

    @property
    def cleanup_event(self):
        return self._cleanup_event

    @property
    def cleanup_done_event(self):
        return self._cleanup_done_event

    def clean_all_objects(self):
        """Signals the event that triggers cleanup, and
        waits for the done event."""
        self.cleanup_event.set()
        self.cleanup_done_event.wait(self._cleanup_done_event_timeout)
        self.cleanup_done_event.clear()

    def run(self):
        """ Do garbage collection.

        @return: None
        @rtype : None

        """
        if not self._created_network_log:
            from utils.logger import create_network_log
            from utils.logger import LOG_TYPE_GC
            create_network_log(LOG_TYPE_GC)
            self._created_network_log = True

        try:
            self.do_garbage_collection()
        except Exception as error:
            error_str = f"{formatting.timestamp()}: Exception during garbage collection: {error!s}"
            print(error_str)
            from utils.logger import garbage_collector_logging as CUSTOM_LOGGING
            CUSTOM_LOGGING(error_str)
            raise

    def finish(self):
        # Move the saved dynamic objects into the dynamic objects
        # cache to be deleted
        for name, val in self.saved_dyn_objects.items():
            if name in self.dyn_objects_cache:
                self.dyn_objects_cache[name].extend(val)
            else:
                self.dyn_objects_cache[name] = val
        self._dyn_objects_cache_size = 0

    def _cache_empty(self):
        """ Helper function that returns whether or not there are any more
            resources to be deleted

        @return: True if there are more resources to be deleted
        @rtype : Bool

        """
        for type in self._destructor_types:
            if len(self.overflowing[type]) > 0 or\
                    len(self.dyn_objects_cache[type]) > 0 or\
                    len(self.async_deletions[type]) > 0:
                return False
        return True

    def do_garbage_collection(self):
        """ Implements the garbage collection logic.

        Very important: DO NOT hold the garbage_collection lock while
                        deleting objects because THIS WILL BLOCK creation and
                        registration of new objects. Holding the lock when
                        flushing overflowing objects from cache
                        to overflowing area, and then let them age there
                        with lock RELEASED is fine.
        @return: None
        @rtype : None

        """
        destructors = {}
        self.dyn_objects_cache_lock.acquire()

        # Try finding matching destructors for instantiated object types.
        # Only use destructors with a single resource type. Any children
        # of parent/child relationships will be deleted when the parent's
        # own destructor is called
        for object_type in self.dyn_objects_cache:
            for req in self.req_collection:
                if req.is_destructor() and \
                len(req.consumes) == 1 and \
                object_type in req.consumes:
                    destructors[object_type] = req
                    # Try to find the DELETE request that seems like it's trying to
                    # delete this object specifically (i.e. the final variable in the endpoint)
                    final_var = req.endpoint.split('/')[-1]
                    if RDELIM in final_var and\
                    final_var.replace(RDELIM, "") == object_type:
                        # Found destructor where the final variable in the endpoint is
                        # the correct type of dynamic object. Stop searching.
                        break

        # Flush garbage_collector registry and RELEASE lock. Then, perform
        # the deletion of the overflowing objects which may take some
        # significant time but at least, since we have released the lock, it
        # won't delay the creation of new objects but only the garbage
        # collection.
        for object_type in destructors:
            if object_type not in self.overflowing:
                self.overflowing[object_type] = []
                self.async_deletions[object_type] = []
                self.gc_stats[object_type] = {}
                self._destructor_types.append(object_type)
            n_overflowing = len(self.dyn_objects_cache[object_type]) -\
                self._dyn_objects_cache_size
            if n_overflowing > 0:
                self.overflowing[object_type].extend(
                    self.dyn_objects_cache[object_type][:n_overflowing]
                )
                self.dyn_objects_cache[object_type] =\
                    self.dyn_objects_cache[object_type][n_overflowing:]

        # apply destructors with lock RELEASED.
        self.dyn_objects_cache_lock.release()
        self.apply_destructors(destructors)

    def apply_destructors(self, destructors, max_aged_objects=100):
        """ Background task trying to delete evicted objects that are in
            @overflowing dictionary.

        @param overflowing: Dictionary of overflowing objects. We need to issue
                                deletes to all these objects
        @type  overflowing: Dict
        @param destructors: The Request class objects required to delete.
        @type  destructors: Dict

        @return: None
        @rtype : None

        NOTE: This function is invoked without any lock since overflowing
        objects are already dead (not referenced by anything) and are just
        aging here.

        """
        from engine.core.async_request_utilities import try_async_poll

        if not self.overflowing:
            return

        from engine.errors import TransportLayerException
        from engine.transport_layer import messaging
        from engine.transport_layer.messaging import HttpSock
        from utils.logger import raw_network_logging as RAW_LOGGING
        from utils.logger import garbage_collector_logging as CUSTOM_LOGGING
        from engine.core import request_utilities

        def update_gc_stats(status_code):
            status_str = str(status_code)
            if status_str not in self.gc_stats[type]:
                self.gc_stats[type][status_str] = 0
            self.gc_stats[type][status_str] += 1

        def process_async_deletes():
            async_deleted_list = []
            # Try to async poll for 1 second, unless GC has been requested after every sequence.
            # When GC runs after every sequence, complete clean-up is desired, so wait for the resource
            # to be deleted for the full the async timeout.
            async_timeout = 1.1
            if Settings().run_gc_after_every_sequence:
                # Wait until the async deletions have completed.
                async_timeout = Settings().max_async_resource_creation_time

            if self.async_deletions[type]:
                CUSTOM_LOGGING("{}: Polling for status of garbage collection of * {} * objects".\
                format(formatting.timestamp(), len(self.async_deletions[type])))

            # Go through the polling requests from the previous time applying destructors
            for value, (rendered_delete_request, response) in self.async_deletions[type]:

                # Get the request used for polling the resource availability
                responses_to_parse, resource_error, polling_attempted = try_async_poll(
                    request_data=rendered_delete_request, response=response, max_async_wait_time=async_timeout,
                    poll_delete_status=True)

                if polling_attempted:
                    status_code = None if not responses_to_parse else responses_to_parse[0].status_code
                    if resource_error or status_code in DELETED_CODES:
                        # The delete operation has finished.
                        if status_code not in DELETED_CODES:
                            # There was a resource error
                            self.num_failed_deletions += 1
                        update_gc_stats(status_code)
                        async_deleted_list.append(value)
                else:
                    # Polling location was not found in the response.
                    # Assume the object has been successfully deleted.
                    async_deleted_list.append(value)
                    update_gc_stats(response.status_code)
            return async_deleted_list

        def process_overflowing():
            deleted_list = []
            if self.overflowing[type]:
                CUSTOM_LOGGING("{}: Trying garbage collection of * {} * objects".\
                format(formatting.timestamp(), len(self.overflowing[type])))
                CUSTOM_LOGGING(f"{type}: {self.overflowing[type]}")

            # Iterate in reverse to give priority to the newest resources
            for value in reversed(self.overflowing[type]):
                rendered_data, _ , _, _, _ = destructor.\
                    render_current(self.req_collection.candidate_values_pool)

                # replace dynamic parameters
                fully_rendered_data = str(rendered_data)
                fully_rendered_data = fully_rendered_data.replace(RDELIM + type + RDELIM, value)

                if fully_rendered_data:
                    # Send the request and receive the response
                    response = request_utilities.send_request_data(
                        fully_rendered_data, req_timeout_sec=Settings().max_request_execution_time,
                        reconnect=Settings().reconnect_on_every_request,
                        http_sock=gc_sock)

                    success = response.status_code is not None
                    if success:
                        self.monitor.increment_requests_count('gc')
                    else:
                        RAW_LOGGING(f"GC request failed: {response.to_str}")

                    # Check to see if the DELETE operation is complete
                    update_gc_stats(response.status_code)
                    if response.status_code in DELETED_CODES:
                        deleted_list.append(value)
                    if response.status_code in DELETED_CODES_ASYNC:
                        # Note: if the DELETE returned a 202, the final status of the deletion must be obtained
                        # by polling.  However, do not wait for each individual DELETE to complete,
                        # since this may stall the GC.  Instead, record the polling location and check the status
                        # on the next collection.
                        self.async_deletions[type].append((value, (fully_rendered_data, response)))
                        deleted_list.append(value)
            return deleted_list

        try:
            gc_sock = threadLocal.gc_sock
        except AttributeError:
            # Socket not yet initialized.
            threadLocal.gc_sock = HttpSock(Settings().connection_settings)
            gc_sock = threadLocal.gc_sock

        # For each object in the overflowing area, whose destructor is
        # available, render the corresponding request, send the request,
        # and then check the status code. If the resource has been determined
        # to be removed, delete the object from the overflow area.
        # At the end keep track of only up to @param max_aged_objects
        # remaining objects.
        for type in destructors:
            destructor = destructors[type]
            deleted_list = process_overflowing()
            async_deleted_list = process_async_deletes()

            # Remove deleted items from the to-delete cache
            for value in deleted_list:
                self.overflowing[type].remove(value)

            # Remove the items that failed to be deleted based on their async status
            self.async_deletions[type] =\
                [(val, x) for (val, x) in self.async_deletions[type] if val not in async_deleted_list]

            # Check how many objects are left in the overflowing list
            # If there are more than the allowed number of objects, terminate the run
            if Settings().max_objects_per_resource_type is not None:
                max_objects_per_resource_type = Settings().max_objects_per_resource_type
                obj_count = len(self.overflowing[type]) + len(self.async_deletions[type]) + self.num_failed_deletions
                if obj_count > max_objects_per_resource_type:
                    raise ResourceTypeQuotaExceededException(f"Limit exceeded for objects of type {type} "
                                                             f"({obj_count} > {max_objects_per_resource_type}).")
                # Since resource limits are being tracked, do not remove any objects from overflowing
            else:
                self.overflowing[type] = self.overflowing[type][-max_aged_objects:]
                self.async_deletions[type] = self.async_deletions[type][-max_aged_objects:]


class GarbageCollectorThread(threading.Thread):
    """ Garbage collector thread class
    """
    def __init__(self, garbage_collector, interval):
        """ Uses requests from @param req_collection to garbage collect, i.e.,
        try to periodically try deleting dynamic objects.

        @param garbage_collector: The garbage collector that will be used to clean up objects.
        @type  garbage_collector: GarbageCollector class object.
        @param interval: The interval after which to restart garbage collection.
        @param interval: Int

        @return: None
        @rtype : None

        """
        threading.Thread.__init__(self)

        self._garbage_collector = garbage_collector
        self._finishing = False
        self._interval = interval

    def run(self):
        """ Thread entrance - periodically do garbage collection.

        @return: None
        @rtype : None

        """
        SequenceTracker.set_origin('gc')
        def _should_stop():
            if self._finishing:
                elapsed_time = time.time() - self._cleanup_start_time
                return elapsed_time > self._max_cleanup_time or self._garbage_collector._cache_empty()
            else:
                return False

        while not _should_stop():
            # Sleep here for _interval unless the cleanup event has been set
            self._garbage_collector.cleanup_event.wait(self._interval)
            try:
                self._garbage_collector.run()
            except Exception as error:
                # Set the cleanup event timeout to a short interval so the Fuzzer thread does not wait
                # after the GC thread is terminated
                self._garbage_collector._cleanup_done_event_timeout = 1
                raise
            finally:
                self._garbage_collector.cleanup_event.clear()
                self._garbage_collector.cleanup_done_event.set()

    def finish(self, max_cleanup_time):
        """ Begins the final cleanup of the garbage collector

        @param max_cleanup_time: The amount of time to continue garbage
                                 collection after this function call
        @type  max_cleanup_time: Integer
        @return: None
        @rtype : None

        """
        self._garbage_collector.finish()

        # The first cycle of garbage collection will run immediately when finishing GC.
        # Set subsequent ones to run at 10 second interval, since the only remaining resources
        # will be async deletions, and they should be attempted with a polling interval
        self._interval = 10
        self._cleanup_start_time = time.time()
        self._finishing = True
        self._max_cleanup_time = max_cleanup_time
        # Set the cleanup event flag to immediately stop the GC loop from waiting
        self._garbage_collector.cleanup_event.set()

