# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Dynamic Variabes a.k.a. dependencies and dynamic objects garbage collection.
"""
from __future__ import print_function
import time
import threading
import sys
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool
import utils.formatting as formatting
from restler_settings import Settings

threadLocal = threading.local()
# Keep TLS tlb to enforce mutual exclusion when using >1 fuzzing jobs.
threadLocal.tlb = {}
tlb = threadLocal.tlb

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
    # thread_id = threading.current_thread().ident
    # print("Getting: {} / Value: {} ({})".format(type, tlb[type], thread_id))
    return str(tlb[type])


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

    # Keep track of all dynamic objects ever created.
    if dyn_objects_cache_lock is not None:
        dyn_objects_cache_lock.acquire()
    if type not in dyn_objects_cache:
        dyn_objects_cache[type] = []
    dyn_objects_cache[type].append(value)
    if dyn_objects_cache_lock is not None:
        dyn_objects_cache_lock.release()

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
DELETED_CODES = ['200', '202', '204', '404']

class GarbageCollectorThread(threading.Thread):
    """ Garbage collector class
    """
    def __init__(self, req_collection, fuzzing_monitor, interval):
        """ Uses requests from @param req_collection to garbage collect, i.e.,
        try to periodically try deleting dynamic objects.

        @param req_collection: The requests collection.
        @type  req_collection: RequestCollection class object.
        @param fuzzing_monitor: The global monitor for the fuzzing run
        @type  fuzzing_monitor: FuzzingMonitor
        @param interval: The interval after which to restart garbage collection.
        @param interval: Int

        @return: None
        @rtype : None

        """
        threading.Thread.__init__(self)

        self._interval = interval
        self._dyn_objects_cache_size = Settings().dyn_objects_cache_size

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
        self._finishing = False
        self._cleanup_event = threading.Event()

    def run(self):
        """ Thread entrance - periodically do garbage collection.

        @return: None
        @rtype : None

        """
        def _should_stop():
            if self._finishing:
                elapsed_time = time.time() - self._cleanup_start_time
                return elapsed_time > self._max_cleanup_time or self._cache_empty()
            else:
                return False

        from utils.logger import create_network_log
        from utils.logger import LOG_TYPE_GC
        create_network_log(LOG_TYPE_GC)

        while not _should_stop():
            # Sleep here for _interval unless the cleanup event has been set
            self._cleanup_event.wait(self._interval)
            try:
                self.do_garbage_collection()
            except Exception as error:
                error_str = f"Exception during garbage collection: {error!s}"
                print(error_str)
                from utils.logger import garbage_collector_logging as CUSTOM_LOGGING
                CUSTOM_LOGGING(error_str)
                sys.exit(-1)

    def _cache_empty(self):
        """ Helper function that returns whether or not there are any more
            resources to be deleted

        @return: True if there are more resources to be deleted
        @rtype : Bool

        """
        for type in self._destructor_types:
            if len(self.overflowing[type]) > 0 or\
                    len(self.dyn_objects_cache[type]) > 0:
                return False
        return True

    def finish(self, max_cleanup_time):
        """ Begins the final cleanup of the garbage collector

        @param max_cleanup_time: The amount of time to continue garbage
                                 collection after this function call
        @type  max_cleanup_time: Integer
        @return: None
        @rtype : None

        """
        # Move the saved dynamic objects into the dynamic objects
        # cache to be deleted
        for name, val in self.saved_dyn_objects.items():
            if name in self.dyn_objects_cache:
                self.dyn_objects_cache[name].extend(val)
            else:
                self.dyn_objects_cache[name] = val

        self._finishing = True
        self._interval = 0
        self._dyn_objects_cache_size = 0
        self._cleanup_start_time = time.time()
        self._max_cleanup_time = max_cleanup_time
        # Set the cleanup event flag to immediately stop the GC loop from waiting
        self._cleanup_event.set()

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
        @param max_aged_objects: Maximum number of objects we allow to age
                                    and will retry to delete (since delete
                                    is idempotent this is fine).
        @type  max_aged_objects: Int

        @return: None
        @rtype : None

        NOTE: This function is invoked without any lock since overflowing
        objects are already dead (not referenced by anything) and are just
        aging here.

        """
        if not self.overflowing:
            return

        from engine.errors import TransportLayerException
        from engine.transport_layer import messaging
        from utils.logger import raw_network_logging as RAW_LOGGING
        from utils.logger import garbage_collector_logging as CUSTOM_LOGGING
        # For each object in the overflowing area, whose destructor is
        # available, render the corresponding request, send the request,
        # and then check the status code. If the resource has been determined
        # to be removed, delete the object from the overflow area.
        # At the end keep track of only up to @param max_aged_objects
        # remaining objects.
        for type in destructors:
            destructor = destructors[type]
            deleted_list = []

            if self.overflowing[type]:
                CUSTOM_LOGGING("{}: Trying garbage collection of * {} * objects".\
                format(formatting.timestamp(), len(self.overflowing[type])))
                CUSTOM_LOGGING(f"{type}: {self.overflowing[type]}")

            # Iterate in reverse to give priority to newest resources
            for value in reversed(self.overflowing[type]):
                rendered_data, _ = destructor.\
                    render_current(self.req_collection.candidate_values_pool)

                # replace dynamic parameters
                fully_rendered_data = str(rendered_data)
                fully_rendered_data = fully_rendered_data.replace(RDELIM + type + RDELIM, value)

                if fully_rendered_data:
                    try:
                        # Establish connection to the server
                        sock = messaging.HttpSock(Settings().connection_settings)
                    except TransportLayerException as error:
                        RAW_LOGGING(f"{error!s}")
                        return

                    # Send the request and receive the response
                    success, response = sock.sendRecv(fully_rendered_data)
                    if success:
                        self.monitor.increment_requests_count('gc')
                    else:
                        RAW_LOGGING(response.to_str)

                    # Check to see if the DELETE operation is complete
                    try:
                        if response.status_code in DELETED_CODES:
                            deleted_list.append(value)
                    except Exception:
                        pass

            # Remove deleted items from the to-delete cache
            for value in deleted_list:
                self.overflowing[type].remove(value)
            self.overflowing[type] = self.overflowing[type][-max_aged_objects:]
