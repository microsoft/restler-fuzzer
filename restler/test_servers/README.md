## To run example in test mode:

```
python -B C:\...restler\restler.py --fuzzing_mode directed-smoke-test --restler_grammar c:\...restler\test_servers\unit_test_server\test_grammar.py --custom_mutations c:\...restler\test_servers\unit_test_server\test_dict.json --use_test_socket --garbage_collector_interval 30
```

test_grammar.py can be updated as any typical RESTler grammar.
The Test server's current valid resource tree is like so:

```
city->house->color
    ->road
farm->animal
item
```

test_grammar.py should pass the smoke test with 33/33 requests rendered,
but the server is intentionally not free of errors.
To return a test with planted bugs, run the same command with test_grammar_bugs.py:
```
python -B C:\...restler\restler.py --fuzzing_mode directed-smoke-test --restler_grammar c:\...restler\test_servers\unit_test_server\test_grammar_bugs.py --custom_mutations c:\...restler\test_servers\unit_test_server\test_dict.json --use_test_socket --garbage_collector_interval 30 --enable_checkers leakagerule useafterfree resourcehierarchy
```


## To create a new custom test server:
* Create a new directory under test_servers for the code.
* Have your new server class inherit from test_servers.test_server_base.TestServerBase
* Implement the abstract parse_message function,
which is what the socket will call from its sendall function.
  * Use this to trigger all of your server-side logic.
  The parse_message function takes the actual request string as its input, so treat it as though you are receiving a message from the socket.
* Simply set the self._response HttpResponse variable when you are done processing the data.
  * This _response will be returned as the server's response from the socket's recv function.
  * Note that the default behavior is for the response to be deleted after recv is called,
  so you will want to overwrite TestServerBase's response property if this is not the desired behavior.
  * The HttpResponse object can take the full response string when initialized or it can be initialized empty and you can set ._status_code, ._str, and/or ._body manually.
* Any of the TestServerBase functions can be overwritten by your new class, if necessary.
* All private functions in TestServerBase are intended to be used by your sub-class when appropriate.
  * These are denoted by a leading underscore in the function name

# To use default resource logic:
* Create a new resource module in your test server's directory
* Create individual resources types that inherit from test_servers.resource_base.ResourceBase
  * The ResourceBase logic works as a tree, starting with a root that has self._children resources,
  each of which have their own self._children resources.
  Example: ResourcePool (root) contains City and Animal resources.
  City contains Road children and Animal contains no children.
  See unit_test_resources for an example.
* Each ResourceBase contains a 'data' dict member variable that contains only 'name' by default.
* ResourceBase is an abstract class and requires each resource to create its own set_resource function.
  * The set_resource function is used to add a new resource as a child of a current resource.
  See unit_test_resources for an example.
* The get_resources function in ResourceBase should be passed the dynamic object list up until the final (child) resource name.
If the final dynamic object in the list is actually a type and not a resource by name,
simply call get_resources on the dynamic object list, omitting the final object.
In other words, if the dynamic object list is an odd number, omit the final object.
This returns the final (child) resource.
You will then want to call get_data() on that returned resource to get its data.
  * To get data only for a 'type', you will want to call get_data(type) on the returned resource.





