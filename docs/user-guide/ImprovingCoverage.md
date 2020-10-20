# Improving API Coverage

This page outlines strategies and techniques for improving RESTler's API coverage.

There are several approaches for improving coverage.  The most efficient approach will depend on the size and complexity of the API, and the type of errors encountered.

**Fixing errors with the most bug buckets**

RESTler contains a 'Results analyzer' that parses the logs and bucketizes responses based on the status code and message text.   See [ResultsAnalyzer](ResultsAnalyzer.md) for more details.  The analyzer produces two files:

-  ```ResponseBuckets/runSummary.json```:  contains the bucket IDs and counts
-  ```ResponseBuckets/errorBuckets.json```:  contains the bucket descriptions.

When fixing errors to improve coverage, we recommend starting with errors that have the highest count.  Another approach is to quickly look over the ```errorBuckets.json``` and fix easy to address errors, based on domain knowledge for the particular API.  Note: since these files do not contain information about request sequences, you may still need to analyze RESTler's raw network logs to understand errors involving state (e.g. 'resource cannot be used because it is still being created').

**Fixing errors sequentially**

Another approach is to navigate RESTler's raw network log sequentially, and fix failing requests one by one by searching for "*Received*: " in the ```network.testing.*.txt``` log, and individually analyzing requests with failure status code responses.  This is a good initial approach if code coverage is very low.

**Fixing missing producer-consumer dependencies**

If requests are failing because dependent resources are not created, or the value passed in a particular parameter does not correctly refer to a dependent resource, this can mean that dependencies are not correctly inferred between requests.  While RESTler could not *automatically* determine how to use the API to create a pre-requisite resource that is required for this request, you may be able to manually configure RESTler so more dependencies are identified.  This approach is typically used after gaining more experience with RESTler using the two strategies above.

To analyze the grammar directly, use one of these two files:

- ```grammar.json```: The RESTler grammar in json format.
- ```grammar.py```: The RESTler grammar in python, generated from grammar.json.

One quick analysis of the grammar that can be done to check if a path parameter is set to '*fuzzstring*'.  Such cases often require extra configuration, such as

- setting a *restler_custom_payload* or *restler_custom_payload_uuid_suffix* for this parameter in the dictionary (see [FuzzingDictionary](FuzzingDictionary.md))
- adding a *producer-consumer annotation* to retrieve the value from a response of a different request in he API (see [Annotations](Annotations.md)).

In some cases, it is more convenient to analyze the grammar since it does not require invoking the API.  However, for a complex API with many parameters, analyzing live logs rather than the grammar is recommended.

## Additional tips

* If the results analyzer failed to produce output (```errorBuckets.json``` is not present), try running it on a network log manually

  ```C:\RESTler\resultsAnalyzer\Restler.ResultsAnalyzer.exe analyze <networklogpath.txt>```

* Try to identify any failing POST or PUT requests that produce resources used by lots of other requests
  * Example: if much of the API updates a "site" resource, that "site" resource needs to be created successfully
  * Such requests will appear as *INVALID* in the file ```main.txt```
  and in the order in which they are required to satisfy producer-consumer dependencies.
  In other words, failing POST or PUT requests (producers) that prevent the subsequent execution of many other requests (consumers)
  will appear first in ```main.txt```.

* If a resource that was once created successfully begins to fail creation due to a limit,
  try using the *create-once* option specified in the engine settings.

* Check ```async_log.txt```. If a resource timed out during creation,
try adding its endpoint to *per_resource_producer_timing_delay* in the *per_resource_settings* (see [SettingsFile](SettingsFile.md)) with a very long (1 hour+) delay.

  * Inspect the log at the end to see how long it actually took to create.
  If it took longer than a couple of minutes, consider adding it to create-once for future runs.
  **Note**: when using create-once the request will not get fuzzed,
  as the request will only be sent once at the beginning of the run and never again.

* RESTler's replay functionality can be used to test small changes without running through the entire test.

  * See [Replay](Replay.md).  This is a quick way to send sequences without using postman/curl
    or trying to edit the grammar.

## How to make updates to improve coverage

Once the problem that causes a request to fail in the Test phase is identified, there are several places in the RESTler workflow that a fix can be made.  The preferred way to fix any error is to fix the inputs to the 'compile' phase, namely the Swagger/OpenAPI specification or a configuration file (e.g., dictionary, annotations, or engine settings).  The reason for this is that such fixes are likely to continue to work when unrelated parts of the API specification are modified, while patching the grammars manually will require maintaining those patches with every change to the API specification.

**Preferred order of updates**

1. Swagger Spec
   - Fix any obvious swagger issues first.
     For example, if response schemas are missing,
     RESTler will not be able to infer producer-consumer dependencies
     and you will see many 'fuzzstring' parameter values as a result.

2. API Examples
   - Adding examples can help RESTler fill in required specific constants (i.e. "magic values")
3. Custom Annotations
   - Annotations can be helpful for defining new producer/consumer relationships,
     specifying different paths for existing producer-consumer relationships,
     or excluding certain endpoints from analysis ("the 'except' feature")
4. Fuzzing Dictionary (pre-compilation)
   - Add custom payloads to the dictionary prior to compilation to populate any values not handled by the swagger or examples.
5. Grammar.json
   - Although created by compilation, this can be edited and recompiled into a new grammar.py.
     Make any quick-and-dirty grammar updates here instead of grammar.py, so they stay in sync.
     See 'Problems/Solutions for the grammar' below for examples of when to use this.
6. Fuzzing Dictionary (post-compilation)
   - If the custom_payload_uuid4_suffix values that were created by the compiler are not correct, update them here.
     For example, if a strict naming convention is required,
     modify the value auto-generated for the custom payload.
7. Grammar.py
   - Because this will always be overwritten by a new compilation it should be the last thing updated.
     Most things in grammar.py can, and should, be updated in grammar.json instead, so they stay in sync.
     This is, however, an easy place to update response parsers
     if the default way the responses are parsed must be modified,
     e.g. due to custom encoding.



## Problems/Solutions for the grammar

Below are solutions for fixing problems that you may find in the grammar.
In most cases, the grammar does not need to be modified directly to fix the issue.

* You want to consume an existing dependency in another position in the request
  * Create a restler annotation with the correct producer/consumer relationship
* A fuzzable or constant value should be some other known value
  * Add that path as a custom payload in the dictionary and recompile
* A fuzzable or constant value should be one of group of values
  * Add that path as a custom payload and include all of the possibilities in the custom payload list
* The incorrect values are being parsed out of a response
  * Create a restler annotation that specifies the correct producer_resource_name
* A body contains unnecessary parameters
  * If you are already using an example payload,
  remove these parameters from the payload.
  This will remove them from the schema used to test the request.
  Note: there is a separate fuzzing mode that will still exercise all the parameters,
  even the ones not included in the example.
  If there are many such parameters,
  we recommend adding an example payload and starting with very few parameters to get the request to succeed
  (Note: this can be done outside the Swagger definition via a RESTler-only local examples.json settings file).
  For a very quick change, in grammar.json, you can carefully delete the unnecessary parameters,
  but remember this change is not persisted on recompilation of the swagger.
* You want to consume a value from a non-producing response (like a GET)
  * Create a restler-annotation with the correct producer/consumer relationship

