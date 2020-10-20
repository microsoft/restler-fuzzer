# Frequently Asked Questions on RESTler

## Q: What is the difference between RESTler and Web Scanners?

RESTler and Web-site scanners are complementary. They find different types of bugs.

Web scanners crawl and scan (HTML, JS, etc.) web-sites pages for security vulnerabilities like XSS attacks and SQL injections. When hitting a REST API, Web Scanners only scans the 'surface' of the API, but they do not generate sequences of requests to exercise more deeply the API and the service behind it.

In contrast, RESTler is specifically designed to automatically test services behind REST APIs by generating sequences of requests and looking for "500 Internal Server Error" bugs, as well as violations of different kinds of properties using API checkers, such as UseAfterFree, NameSpaceRule, ResourceHierarchy, LeakageRule, InvalidDynamicObjects, and PayloadBody violations.

(RESTler was actually created precisely to fill up the gap due to poor handling and coverage of REST APIs by existing Web Scanners...)


## Q: Why can't RESTler always cover all the requests in a Swagger spec?

 RESTler may not figure out automatically how to execute correctly some REST API requests, because missing/incorrect information or examples in the Swagger spec, or because some external dependencies (for instance, when a valid IP address, account, etc. needs to be pre-provisioned and specified in the body of a request). Such problematic requests are typically POST or PUT requests with complex bodies. Moreover, whenever RESTler does not know how to successfully execute a POST/PUT request, it also cannot execute successfully the corresponding PATCH, GET and DELETE requests, so coverage goes down by 4. Plus, any child resources are also not covered. This adds up and leads to lower coverage. 

However, a little nudge by an API expert can often improve the grammar and boost coverage significantly. See ​how to [improve API coverage](ImprovingCoverage.md).​

## Q: Why should I fix "500 Internal Server Errors"?

"500 Internal Server Errors" are unhandled exceptions which can sometimes severely deteriorate service health, for instance, because of resource leaks or due to unintended aborts of expensive operations. They can easily be weaponized (e.g., a simple script can repeatedly trigger one or several of those bugs thousands or millions of times – what would be the impact to service health?). They could also be triggered accidentally at any time by a new workload/user. If the service is critical and outages are not tolerated, they should be fixed (easier to fix than risk a live incident).

Moreover, crashes can sometimes trigger new types of *resource leaks*. Here is an example of bad scenario we have seen and worry about:

    YourService(inputs){ // inputs are untrusted, passed through a REST API
        x,y,z = Parse(inputs)
        Allocate(resourceTypeA, x) // resource A could be a VM
        Allocate(resourceTypeB, y) // resource B could be a storage blob
        Allocate(resourceTypeC, z) --->  crash because of badly formed z
    }

If the last line crashes, the resources of types A and B previously allocated are now leaking. This is a logic bug, and whether this code is managed or native is irrelevant.

## Q: RESTler didn't find any bugs.  What can I do to improve the fuzzing?

Below are several approaches to try to find more bugs with RESTler.

1. Increase your API coverage.  
   
   - Make sure all requests are executed at least once (ideally, successfully) in the 'Test' run (see ImprovingCoverage.md).  
2. Check for corruption bugs that cause all requests to fail.
   
   - If coverage is good, also confirm you get the same request coverage in the 'Fuzz' run by viewing the summary.  It is possible that a bug is triggered during the 'Fuzz' run which causes a subset of requests to always fail or no longer be executed.  For example, if all requests start returning "400" after a corruption in the backend, RESTler will not detect any bugs and will simply keep fuzzing.   Another variant of this is if all requests start returning 404 because authentication has been corrupted (but the authentication script continues to work).
3. Add more invalid dictionary payloads.  
   
   - Add invalid values to the fuzzable types or *restler_custom_payload* values in the dictionary.  Note: for custom payload values, never remove values, because this will cause the dependent requests to fail and reduce coverage.
4. Increase the number of combinations of parameters that are tried.
   
- See [Engine Settings](SettingsFile.md) 
  
5. Increase the time budget.

6. Implement your own checker.  See [Checkers](Checkers.md) for further details.

## Q: What is the difference between using Examples vs. the Fuzzing Dictionary to customize the fuzzing payloads?

Examples and the fuzzing dictionary both allow you to customize the values that will be
sent in the request parameters.  Below, we summarize the main differences between their use cases.

- The fuzzing dictionary is intended for assigning values to individual parameters.  They may be assigned
globally by name (e.g. all properties named ```api-version``` should have the dictionary values), or
by a specific path to a property in the body (e.g., only ```/this/specific/property/api-version``` should have the dictionary values).  The dictionary allows providing hand-crafted interesting fuzzable values, or required "magic values," for specific parameters.  The fuzzing dictionary cannot express dependencies between different parts of the payload.

- The examples are intended to provide a full payload that RESTler should send.  This is primarily used to
specify a valid sub-schema and dependent magic values in the payload in order to have the request succeed.
At time of this writing, such constraints cannot be expressed in the Swagger/OpenAPI specification.  While
it is possible to specify more complex payloads by their raw json value in the dictionary, the examples
should be used for such payloads, because the RESTler payload body fuzzing will be fully aware of the example schema and intelligently fuzz the examples (it does not do so with raw dictionary values).

- In both cases, you may need to have one dictionary (or examples) for the 'Test' phase (to maximize coverage quickly), and another larger set of dictionary values (or examples) with added invalid payloads
for more thorough fuzzing.

- The examples currently require modifying the Swagger definition, but this limitation will be removed in the future.
