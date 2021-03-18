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

### grammar_schema: string (default None)
The path to the grammar.json file for the API in test.
This is required when using the examples and payload body checkers.

### host: string (default None)
Set to override the Host that's specified in the grammar

### include_user_agent: bool (default True)
Set to false to disable sending user agent with requests

### max_async_resource_creation_time: float (default 20)
The maximum amount of time, in seconds, to wait for a resource to be created before continuing.

### max_combinations: int (default 20)
The maximum number of parameter value combinations for parameters within a given request payload.

### max_request_execution_time: float (default 120, max 600)
The maximum amount of time, in seconds, to wait for a response after sending a request.

### no_ssl: bool (default False)
Set to True to disable SSL for requests

### path_regex: str (default None=No regex filtering)
Filters the grammar to only use endpoints whose paths contain the given regex string.

### request_throttle_ms: float (default None)
The time, in milliseconds, to throttle each request being sent.
This is here for special cases where the server will block requests from connections that arrive too quickly.
Using this setting is not recommended.

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

## Per resource settings:
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
            "create_once": 1
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