# RESTler Settings File
The settings file is used to specify customizable settings for RESTler.
This format is in json and will be described below, in detail.
Using the settings file is optional and all settings contained within are optional.
When using the settings file, pass its path as a command-line argument, as follows:

`Restler.exe fuzz --settings C:\somedir\restler_user_settings.json`

If any setting is specified in both the settings file AND as a command-line argument,
the settings file setting will take precedence.

## Settings Options:
### checkers: dict(dict()) (default empty)
The checker specific arguments.
This is a dict type object where the keys are the checker's "friendly name",
which is the checker's name without the word Checker (i.e. payloadbody or invaliddynamicobject).
The values are another dict type object where the keys are a checker-specific argument name
and the value is the argument value, which may be of any type.
Example: {"mode":"exhaustive"}

Checkers' Friendly Names:
* LeakageRule
* ResourceHierarchy
* UseAfterFree
* NamespaceRule
* InvalidDynamicObject
* PayloadBody
* Examples

### client_certificate_path: str (default None)
Path to your X.509 certificate file in PEM format.

If provided and valid, RESTler will attempt to use it during the SSL handshake.

### client_certificate_key_path: str (default None)
Path to your key file in a txt file.

If provided and valid, RESTler will attempt to use it during the SSL handshake.

### authentication: dict (default empty)
Settings for specifying authentication. See [Authentication](Authentication.md) for details

#### _token_ dict (default empty): Can optionally provide one of {```location```, ```token_refresh_cmd```, ```module```}

__location__ str (Default None): File path to a text file containing a token

```json
"authentication": {
    "token": {
      "location": "/path/to/authentication_token.txt",
      "token_refresh_interval":  300
    }
}
```

__token_refresh_cmd__ str (Default None): The command to execute in order to refresh the authentication token

```json
"authentication": {
    "token": {
      "token_refresh_cmd": "python unit_test_server_auth.py",
      "token_refresh_interval": 300
    }
}
```

__module__ dict (Default None): Dictionary containing settings for RESTler to invoke user-specified module to refresh the authentication token
```json
"authentication": {
    "token": {
      "module": {
        "file": "/path/to/unit_test_server_auth_module.py",
        "function": "acquire_token_data",
        "data": {
            "client_id": "client_id"
        }
      },
      "token_refresh_interval": 300
    }
}
```

```file``` str (default None): File path to python file containing function that returns a token

```function``` str (default "acquire_token"): Name of function in file that returns a token. The function must accept two parameters "data", a Dictionary containing the json payload specified under data, and "log" a method that will write any logs to a network auth text file

```data``` dict (Default None): Optional data payload to provide to function. If data is included, RESTler will attempt to call function with data as an argument

__token_refresh_interval__ int (default None): Required parameter if using token authentication. The interval between periodic refreshes of the authentication token, in seconds

#### _certificate_ dict (Default empty): Can optionally provide certificate for SSL handshake

__client_certificate_path__ str (default None): Path to your X.509 certificate file in PEM format. If provided and valid, RESTler will attempt to use it during the SSL handshake

__client_certificate_key_path__ str (default None):  Path to your key file in a txt file. If provided and valid, RESTler will attempt to use it during the SSL handshake

```json
"authentication": {
    "certificate": {
          "client_certificate_path": "/path/to/file.pem",
          "client_certificate_key_path": "/path/to/file.key"
    }
}
```

### custom_bug_codes: list(str)
List of status codes that will be flagged as bugs.

Note:

Use wildcard '\*' to allow any value after the star to exist.
Ex: '2*' will match 200, 201, 210, etc.

Use wildcard '?' to allow any value in that specific location.
Ex: '2?1' will match 201 or 211, but not 202.

### custom_checkers: list(str) (default None)
List of paths to custom checker files that will be loaded during runtime.

### custom_non_bug_codes: list(str)
A list of "non-bug" status codes.
When this setting is defined,
any status code received from the service-in-test that was _not_ included in this list will be flagged as a bug.

Note:

Use wildcard '\*' to allow any value on or after the star to exist.
Ex: '2*' will match 200, 201, 210, etc.

Use wildcard '?' to allow any value in that specific location.
Ex: '2?1' will match 201 or 211, but not 202.

### disable_cert_validation: bool (default False)
Disable TLS certificate validation.

### dyn_objects_cache_size: int (default 10)
Max number of objects of one type before deletion by the garbage collector

### fuzzing_mode: str (default bfs)
The fuzzing mode. Options are:
* bfs
* bfs-cheap
* random-walk
* directed-smoke-test

### garbage_collection_interval: int (default None)
Length of time between garbage collection calls (seconds, None = no garbage collection)

### run_gc_after_every_sequence: bool (default False)
If True, clean up dynamic objects after every sequence, instead of asynchronously
at every ```garbage_collection_interval```.

### max_objects_per_resource_type: int (default None)
If specified, RESTler checks how many objects of each resource type
are left after each garbage collection and fails if the count for any resource type
exceeds the maximum.

### garbage_collector_cleanup_time: int (default 300)
Length of time the garbage collector will attempt to cleanup remaining resources
at the end of fuzzing (seconds)

### global_producer_timing_delay: int (default 0)
The global producer timing delay that is applied to all producers.
Producer timing delay is a wait time (in seconds)
that is applied after any request that is marked as a producer.
This wait time will occur for every request in a sequence except the last request.
The per-resource producer timing delay (below) will override this value.

### reconnect_on_every_request: bool (default False)
By default, RESTler re-uses the same connection across different requests,
re-creating it only on error.  Set to True to create a new connection for
every request sent.

### grammar_schema: string (default None)
The path to the grammar.json file for the API in test.
This is required when using the examples and payload body checkers.

### host: string (default None)
Set to override the Host that's specified in the grammar.

Example: `management.web.com`

(Note: do NOT include https:// or slashes here!)

### basepath: string (default None)
Set to override the basepath that is specified in the grammar.

Example: `/api/v2`

### include_user_agent: bool (default True)
Set to false to disable sending user agent with requests.

### include_unique_sequence_id: bool (default True)
When set, adds a header `x-restler-sequence-id` to each request sent.  The header value is
a unique GUID that identifies the current request sequence.

### user_agent: string (default None)
Set to send a custom user agent with requests.
When specified, overrides the default user agent sent when ```include_user_agent``` is enabled.

### max_async_resource_creation_time: float (default 20)
The maximum amount of time, in seconds, to wait for a resource to be created before continuing.

### max_combinations: int (default 20)
The maximum number of parameter value combinations for parameters within a given request payload.

### test_combinations_settings: dict (default empty)
The settings for advanced testing of parameter combinations.

__header_param_combinations__
Testing
different combinations of headers is supported via the following property:
```json
"test_combinations_settings": {
     "header_param_combinations": {
      "max_combinations": 50,
      "param_kind": "optional"
    }
}
```
The supported ```param_kind``` values are 'optional', 'required', and 'all'.

- optional: test all combinations of optional parameters, always sending the required parameters.
- required: test combinations of required parameters, and omit all optional parameters.
- all: test all combinations of headers, regardless of whether they are required or optional.

__query_param_combinations__
Testing
different combinations of queries is supported via the following property:
```json
"test_combinations_settings": {
     "query_param_combinations": {
      "max_combinations": 50,
      "param_kind": "required"
    }
}
```
The supported ```param_kind``` values are 'optional', 'required', and 'all'.  These have the same meaning as for
header parameter combinations (see above).

__example_payloads__

For request types where one or more examples are provided, this option enables
testing all of the examples instead of just the first one.

```json
"test_combinations_settings": {
      "example_payloads" : {
          "payload_kind": "all"
      }
}
```
The supported ```payload_kind``` value is 'all'.

__max_schema_combinations__
When RESTler explores more than one schema (for example, because parameter
combinations are being tested, as specified in ```test_combinations_settings```),
this option limits the number of schemas that will be tested.

__max_examples__
For request types where one or more examples are provided, this option limits
the number of examples that will be tested.

### max_sequence_length: int (default 100)
The maximum length of fuzzed request sequences.

### add_fuzzable_dates: bool (default False)
Set to True to generate additional dates
near the current date (e.g. one in the future) that will be used for fuzzable date types in addition to
the values specified in the dictionary.
Since some API parameters require a current or future date,
this setting can be used to generate those values, without having to modify the dictionary.
When enabled, the date component of example values is also updated to be a future date.

### max_request_execution_time: float (default 120, max 600)
The maximum amount of time, in seconds, to wait for a response after sending a request.

### no_ssl: bool (default False)
Set to True to disable SSL for requests

### path_regex: str (default None=No regex filtering)
Filters the grammar to only use endpoints whose paths contain the given regex string.

Example: `(\w*)/virtualNetworks/(\w*)`

Example: `disk|virtualNetwork`

### include_requests: list (default empty list=No filtering)
Filters the grammar to include only the specified endpoints and methods.  If no ```methods``` key is specified, all methods are included.
Note: if the included request depends on pre-requisite resources that are created by other
requests, all requests required to create the dependency will be exercised. For example, the endpoint
below requires a ```postId``` that is obtained by executing ```POST /api/blog/posts``` - this request will
also be executed, even though it is not included in the list below.  A future improvement will filter out
such requests from fuzzing, but currently they will be fuzzed as well.

```json
  "include_requests": [
    {
      "endpoint": "/api/blog/posts/{postId}",
    },
    {
      "endpoint": "/api/blog/posts/*",
    }
  ]
```

### exclude_requests: list (default empty list=No filtering)
Filters the grammar to exclude the specified endpoints and methods.

Note: although the ```DELETE``` is excluded from fuzzing below, it will still be executed by the RESTler
garbage collector to clean up the blog posts that were created in order to test the other requests with
endpoint ```/api/blog/posts/{postId}```.  To completely exclude ```DELETE```s from running, you must filter them
manually from grammar.py.

```json
  "exclude_requests": [
    {
      "endpoint": "/api/blog/posts/{postId}",
      "methods": ["GET", "DELETE"]
    }
  ]
```

### save_results_in_fixed_dirname: bool (default False)
Save the results in a directory with a fixed name (skip the 'experiment\<pid\>' subdir).

### disable_logging: bool (default False)
Set to True to disable logging to the network logs and main.txt.

### use_trace_database: bool (default False)
Set to `True` to enable structured logging for all request/response pairs.

The data is logged to a `trace database`, which contains all of the same request/response pairs
that are logged to the network.*.txt logs.
The default format is newline-delimited json, but custom logging formats are supported
via a module specified in the engine settings.

Below is an example request/response pair recorded for demo_server.

```json
{
    "sent_timestamp": "2023-11-02T10:10:59.544824+00:00",
    "received_timestamp": null,
    "request": "GET /api/blog/posts?page=1&per_page=1 HTTP/1.1\r\nAccept: application/json\r\nHost: localhost\r\nContent-Length: 0\r\nr\n\r\n",
    "response": null,
    "request_json": null,
    "response_json": null,
    "tags": {
        "request_id": "27f9653431313fdc3fecc4a890b72b80b4ce1e59",
        "sequence_id": "fe2172ab-151c-419f-b918-f3e7483b3230",
        "combination_id": "1950cbddab7726489624c3d346d3426561c921ad_1",
        "hex_definition": "6daf8d22c7a6b3472fc83c9f08f290b3507c3ff3",
        "origin": "main_driver"
    }
}
```

```json
{
    "sent_timestamp": null,
    "received_timestamp": "2023-11-02T10:10:59.597613+00:00",
    "request": null,
    "response": "HTTP/1.1 400 Bad Request\r\ndate: Thu, 02 Nov 2023 10:10:58 GMT\r\nserver: uvicorn\r\ncontent-length: 41\r\ncontent-type: application/json\r\n\r\n{\"detail\":\"per_page must be at least 2.\"}",
    "request_json": null,
    "response_json": null,
    "tags": {
        "request_id": "27f9653431313fdc3fecc4a890b72b80b4ce1e59",
        "sequence_id": "fe2172ab-151c-419f-b918-f3e7483b3230",
        "combination_id": "1950cbddab7726489624c3d346d3426561c921ad_1",
        "hex_definition": "6daf8d22c7a6b3472fc83c9f08f290b3507c3ff3",
        "origin": "main_driver"
    }
}
```

### trace_database: dict (default empty)

Dictionary containing settings for the trace database.

`file_path` str (default None):  When specified, writes the trace database contents to the specified file.  This option enables re-using the same database for multiple RESTler runs.  Concurrent runs are not currently supported.

`root_dir` str (default None): The directory to which the trace database files should be written.

`custom_serializer` dict (default empty): Dictionary containing settings for the custom serializer.  It must contain the `module_file_path` property, which specifies the path to the module that implements the custom serializer.  The module must contain a class that inherits from the `TraceLogWriterBase` abstract base class (and optionally `TraceLogReaderBase`).  The user may provide additional settings in this dictionary, which will be passed into the serializer class initializer.

`cleanup_time` float (default 10): The maximum amount of time, in seconds, to wait for the data serialization to be complete before exiting.

### request_throttle_ms: float (default None)
The time, in milliseconds, to throttle each request being sent.
This is here for special cases where the server will block requests from connections that arrive too quickly.
Using this setting is not recommended.

### custom_retry_settings: dict (default empty)

The settings for specifying custom status codes or status text on which to re-try the request.  These
override the default values.

__status_codes__

A list of response status codes on which the request should be re-tried may be specified as follows
(shown below with the default value):

```json
"custom_retry_settings": {
     "status_codes": [
         "429"
     ]
}
```

__response_text__

A list of strings in the response on which the request should be re-tried may be specified as follows
(shown below with the default value):

```json
"custom_retry_settings": {
     "response_text": [
         "AnotherOperationInProgress"
     ]
}
```

__interval_sec__

The number of seconds to wait between retries (shown below with the default value).

```json
"custom_retry_settings": {
     "interval_sec": 5
}
```


### target_ip: str (default None)
The IP address of the target webserver.

### target_port: int (default None)
The port of the target webserver.

### time_budget: float (default 1 hour)
Once this time is reached, the fuzzing will stop.
Time is in hours.

### token_refresh_cmd: str (default None)
The command to execute in order to refresh the authentication token.

### token_refresh_interval: int (default None)
The interval between periodic refreshes of the authentication token,
in seconds.

### wait_for_async_resource_creation: bool (default True)
When set, polls for async resource creation before continuing

### ignore_decoding_failures: bool (default False)
Set to True to ignore socked data decoding failures
See: https://github.com/microsoft/restler-fuzzer/issues/164

## Per resource settings
Certain settings can be applied to specific endpoints.
These settings a defined in a per_resource_settings dict.
For example:
```
"per_resource_settings": {
    "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/dnsZones/{zoneName}/{recordType}/{relativeRecordSetName}" : {
        "producer_timing_delay": 5,
        "create_once": 1
    }
}
```
The above snippet will set the producer timing delay to 5 and
activate create-once for the specified endpoint.
Per resource settings override any global settings.

## Sequence exploration settings
The following settings can be applied to control how RESTler
executes request sequences.

__create_prefix_once__
For requests that have dependencies on pre-requisite resources,
RESTler executes the entire sequence of requests required to fuzz
the current request every time it fuzzes the request,
except for if the request type has a ```GET``` or ```HEAD``` method.
This default maximizes reproducibility.  ```GET``` and ```HEAD``` methods
are assumed to have no side effects on the resources created by the API,
so pre-requisite resources are not re-created when fuzzing them.

All requests prior to the current request being fuzzed (the _sequence prefix_) can either be re-executed every time, or saved for testing all combinations of the current request.  This can be controlled on a per-method or per-endpoint basis, as follows.

1. Execute the entire sequence, except for
requests with `GET` methods.

```json
  "sequence_exploration_settings": {
    "create_prefix_once": [
      {
          "methods": ["GET"],
          "endpoints": "*",
          "reset_after_success": false
      }
    ]
  }
```

2.  Always execute the entire sequence for every combination.
Providing an empty list overrides the default behavior as described earlier.

```json
  "sequence_exploration_settings": {
    "create_prefix_once": [
     ]
  }
```

3. Do not re-execute the entire sequence for a specific resource.
```json
  "sequence_exploration_settings": {
    "create_prefix_once": [
      {
          "methods": ["GET", "PUT", "PATCH"],
          "endpoints": ["/customer/{customerId}"],
      }
    ]
  }

```

4. Do not re-execute the entire sequence in all cases, except when a successful request deletes or modifies the pre-requisites set up by the previous requests.
```json
  "sequence_exploration_settings": {
    "create_prefix_once": [
      {
          "methods": ["GET", "HEAD"],
          "endpoints": "*",
          "reset_after_success": false
      },
      {
        "methods": ["PUT", "POST", "PATCH", "DELETE"],
        "endpoints": "*",
        "reset_after_success": true
      }
    ]
}

```


### producer_timing_delay: int (default global_producer_timing_delay)
The per resource producer timing delay, in seconds.
This is a dict type object where the key is the request's endpoint
and the value is the producer timing delay.
The endpoint can be found in the Swagger file
or the grammar file created from compiling with RESTler.

### create_once: int (default 0)
When set to 1 (or true),
this resource will be created and destroyed only once
at the beginning and end of the fuzzing run.
Note: Its child resources will be fuzzed
and must be separately included in 'create_once' if desired.

### custom_dictionary: string (default None)
If this setting is set with a valid path to a restler mutations dictionary,
the values in that dictionary will be used for the specified resource.
For instance, any custom payloads
or fuzzable values for this endpoint will be taken from the specified custom dictionary
instead of the default dictionary.

### random_seed: int (default 12345)
The random seed to use for the RESTler invocation.  The same random seed will
always be used if none is specified and `generate_random_seed` is `False`.  Checkers may have a separate `random_seed` setting that overrides this setting.

### generate_random_seed: bool (default False)
When `True`, generate a new random seed instead of using the default or user-specified
`random_seed`.  This setting also overrides any `random_seed` checker settings.
The random seed that was used for the run is logged in main.txt as well as in the
testing summary.

### custom_value_generators: string (default None)
If this setting is set to a valid path with a ```.py``` extension,
RESTler will try to import the contents of this
file as a Python module, and will search for a dictionary named ```value_generators```.
This dictionary must have the same structure as the mutations dictionary,
but each entry may be initialized with a generator function (example shown below).
A dynamic value generator overrides the corresponding entry in the custom dictionary, if
it exists.  For example, if a ```restler_custom_payload``` for ```ip_address``` specifies
one value in the dictionary, and has a custom value generator, values will be
dynamically generated up to ```max_combinations``` or until the
generator has no more values.

Below is an example of a valid Python dictionary that specifies a value generator.
Note: a template file containing placeholder custom value generators for all of the
dictionary entries, including custom payloads, is automatically generated
during compilation and placed into the 'Compile' directory.

```python
def generate_strings(**kwargs):
    while True:
        yield "fuzz"
        yield str(random.randint(-10, 10))

value_generators = {
	"restler_fuzzable_string": generate_strings
}
```



## Example Settings File Format
```json
{
    "max_combinations": 20,
    "max_request_execution_time": 90,
    "max_async_resource_creation_time": 60,
    "global_producer_timing_delay": 2,
    "dyn_objects_cache_size":20,
    "fuzzing_mode": "directed-smoke-test",
    "path_regex": "(\\w*)/blog/posts(\\w*)",
    "per_resource_settings": {
        "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/dnsZones/{zoneName}/{recordType}/{relativeRecordSetName}": {
            "producer_timing_delay": 1,
            "create_once": 1,
            "custom_dictionary": "c:\\restler\\custom_dict1.json"
        },
        "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/dnsZones/{zoneName}" {
            "producer_timing_delay": 5
        }
    },
    "checkers": {
        "useafterfree" : {
            "mode" : "exhaustive"
        },
        "leakagerule" : {
            "mode" : "normal"
        },
        "resourcehierarchy" : {
            "mode" : "exhaustive"
        }
    }
}
```
