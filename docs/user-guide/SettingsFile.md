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
Set to false to disable sending user agent with requests

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

For request types where one or more examples are provided, this option enables testing all of
the examples instead of just the first one.

```json
"test_combinations_settings": {
      "example_payloadds" : {
          "payload_kind": "all"
      }
}
```
The supported ```payload_kind``` value is 'all'.


### add_fuzzable_dates: bool (default False)
Set to True to generate additional dates
near the current date (e.g. one in the future) that will be used for fuzzable date types in addition to
the values specified in the dictionary.
Since some API parameters require a current or future date,
this setting can be used to generate those values, without having to modify the dictionary.

### max_request_execution_time: float (default 120, max 600)
The maximum amount of time, in seconds, to wait for a response after sending a request.

### no_ssl: bool (default False)
Set to True to disable SSL for requests

### path_regex: str (default None=No regex filtering)
Filters the grammar to only use endpoints whose paths contain the given regex string.

Example: `(\w*)/virtualNetworks/(\w*)`

Example: `disk|virtualNetwork`

### save_results_in_fixed_dirname: bool (default False)
Save the results in a directory with a fixed name (skip the 'experiment\<pid\>' subdir).

### disable_logging: bool (default False)
Set to True to disable logging to the network logs and main.txt.

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

### time_budget: float (default 30 days)
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
    "path_regex": "(\\w*)/ddosProtectionPlans(\\w*)",
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
