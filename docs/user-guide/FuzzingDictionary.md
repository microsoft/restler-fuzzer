# Fuzzing Dictionary

The fuzzing dictionary allows users to configure sets of values for specific data types or individual parameters.  

There are three categories of configurable values in the dictionary:

1. **Data type**: Values to use for every parameter or property with the given data type.  These will be used when no other values are configured.
2. **Unique id**: A specific property should be unique on every API invocation.  The dictionary allows specifying a set of constant prefixes.
3. **Custom payload:** A specific property should only be set to this set of values.  This may be configured based on the name or full path to the property (in json pointer format).  Note: to customize an entire body payload with many properties, it is recommended to use examples instead (see [Examples](Examples.md)).



RESTler *automatically* generates references to the dictionary when it compiles a Swagger specification.  The dictionary elements correspond to grammar elements in the RESTler grammar, and will determine part of a payload for one or more requests.  

The following describes how each property in the dictionary is used in a RESTler grammar.  If needed, users may also customize the grammar further by referring directly to the dictionary.

- *restler_fuzzable_string* - specifies a list of constant values.  In the RESTler grammar, some parts of each request may be declared as "fuzzable_string", meaning that this part of the request (such as a query parameter) should be fuzzed.  All of the values in the fuzzing dictionary specified for "fuzzable_string" will be tried.

- *restler_fuzzable_int*, *restler_fuzzable_bool*, *restler_fuzzable_datetime*, *restler_fuzzable_object*, *restler_fuzzable_number*, *restler_fuzzable_uuid4* - same as restler_fuzzable_string, but for the other types named in the suffix.

- *restler_custom_payload* - specifies constants corresponding to "magic values" or pre-provisioned resources that are not created by the API under test.  These are usually single constant values, such as IDs for pre-provisioned resources.  In some cases, a list of strings may need to be specified, for example if an enum specifies dozens of constants, but only a few of them should be used during fuzzing.  Below are a few example custom payloads:

  ``` json 
  {
     "restler_custom_payload": {
         "api-version": "2020-10-27",
         "/feedback/[0]/tags": [ "happy", "sad"]    
     }   
  }
  ```

- *restler_custom_payload_header* - specifies custom header names and sets of values to include as custom headers.

- *restler_custom_payload_uuid4_suffix* specifies constant values to which random GUID values will be appended.


Note: to specify a double-quote " in a string in a fuzzing dictionary, use `\"`

#### **Per resource dictionaries**

Usually, it is sufficient to specify a dictionary for the entire API under test, or one dictionary per API specification when several API specifications are tested together.  However, there may be cases when a specific endpoint requires a different custom payload from the rest of the APIs.  An example of this is when a service uses different API versions for different endpoints in the same API: the ```api-version``` parameter needs to be one of several values, but for specific endpoints, so it cannot be specified in one *restler_custom_payload*.  Such cases are handled with a per-resource dictionary for individual endpoints, which takes precedence over the global dictionary.  See [SettingsFile](SettingsFile.md) for how to configure a per-resource dictionary.   