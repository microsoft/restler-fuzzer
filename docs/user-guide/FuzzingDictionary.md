# Fuzzing Dictionary

The fuzzing dictionary allows users to configure sets of values for specific data types or individual parameters.

RESTler *automatically* generates references to the dictionary when it compiles a Swagger specification.  The dictionary elements correspond to grammar elements in the RESTler grammar, and will determine part of a payload for one or more requests.

There are three categories of configurable values in the dictionary:

1. **Data type**: Values to use for every parameter or property with the given data type.  These will be used when no other values are configured.
2. **Unique id**: A specific property should be unique on every API invocation.  The dictionary allows specifying a set of constant prefixes.
3. **Custom payload:** A specific property should only be set to this set of values.  This may be configured based on the name or full path to the property (in json pointer format).  Note: to customize an entire body payload with many properties, it is recommended to use examples instead (see [Examples](Examples.md)).


## How to configure the dictionary

When you first try RESTler, using the command
    ```restler.exe compile --api_spec <your spec>```,
RESTler will generate a ```Compile``` folder that contains the grammar, plus a
default dictionary ```dict.json``` and ```config.json``` (and several other configuration files).
The latter may be used to customize the fuzzing grammar, by modifying the
configuration files and then re-compiling.

**If you are just adding new values to the dictionary:**

To add more values to the existing lists of values in the dictionary (```restler_fuzzable_string```, etc.): simply copy the dictionary out of the ```Compile```
folder (to avoid accidentally re-compiling and overwriting the dictionary in the future),
modify it, and proceed to testing and fuzzing (see [Testing](Testing.md)).

**If you add a new custom property to the dictionary:**

Sometimes, you need to configure a specific property
to be a certain value, or inject a query/header parameter
that is not declared in the spec.  In this case, you
will be adding new properties to the dictionary custom
payloads.  For example, if you need to use a specific ```api-version```, you may add

```json
"restler_custom_payload" {
      "api-version": ["2021-01-01"]
    }
}
```

<ins>To add new custom payloads, you must follow these steps:</ins>


1.	Copy the ```config.json``` and ```dict.json``` (and possibly ```engine_settings.json``` if you need to modify them) out of this Compile folder.
2.	Change the dictionary as needed.

3.	Change the ```config.json``` path to the dictionary (```CustomDictionaryFilePath```) to
the dictionary you copied and modified in step (2).
4.	Run the ```compile``` command that takes a configuration file as input, ```restler.exe compile config.json```, using the ```config.json``` modified in step (3).  Once you have compiled with the new property, you can add new values to be fuzzed without having to re-compile again.


## Dictionary Properties

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

A special syntax may be used to replace the entire contents
of the body of a request.  For a request with endpoint
```/api/blog/{blogId}``` and method ```GET```, the following replaces the body of this request with the
specified custom payloads.
  ``` json
  {
     "restler_custom_payload": {
         "/api/blog/{blogId}/get/__body__": ["new body"],
         "/api/blog/{blogId}/get/Content-Type": ["xml"]
     }
  }
  ```
The content type may also be replaced using the same syntax, as above.


- *restler_custom_payload_header* - specifies a list of specific values required for header parameters.

  There are two use cases:

  1) specifying values that should be plugged into header parameters which are declared in the spec.  This works in the same way as *restler_custom_payload*.
  2) specifying custom header names that are not included in the specification.  This allows passing in extra custom headers.

  ``` json
  {
     "restler_custom_payload_header": {
         "firstHeader": ["v1"],
         "secondHeader": [ "a", "b"]
     }
  }
  ```

- *restler_custom_payload_query* - specifies a list of specific values required for query parameters.  This property works the same as *restler_custom_payload_header*

  ``` json
  {
     "restler_custom_payload_query": {
         "query_param": ["qp1", "qp2"]
     }
  }
  ```



- *restler_custom_payload_uuid4_suffix* specifies constant values to which random GUID values will be appended.


Note: to specify a double-quote " in a string in a fuzzing dictionary, use `\"`

#### **Per resource dictionaries**

Usually, it is sufficient to specify a dictionary for the entire API under test, or one dictionary per API specification when several API specifications are tested together.  However, there may be cases when a specific endpoint requires a different custom payload from the rest of the APIs.  An example of this is when a service uses different API versions for different endpoints in the same API: the ```api-version``` parameter needs to be one of several values, but for specific endpoints, so it cannot be specified in one *restler_custom_payload*.  Such cases are handled with a per-resource dictionary for individual endpoints, which takes precedence over the global dictionary.  See [SettingsFile](SettingsFile.md) for how to configure a per-resource dictionary.

#### **Dynamically generating values**
RESTler also supports dynamically generating values for most of the data types above.  Each primitive or custom
payload may have a corresponding dynamic value generator.  For more details on how to provide
dynamically generated values to RESTler,
see the ```custom_value_generators``` setting in the [SettingsFile](SettingsFile.md)
