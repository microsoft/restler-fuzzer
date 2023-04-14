# Compiler Configuration options

* *SwaggerSpecFilePath* is an array specifying one or more paths to the API specification.  If multiple files are specified, the fuzzing grammar will contain the union of requests in those Swagger specifications.

    For example:

    ```json
    "SwaggerSpecFilePath": [ "spec1.json", "spec2.json"]
    ```



* *SwaggerSpecConfig* is an alternative to *SwaggerSpecFilePath* (only one of these may be specified).  This is an array specifying one or more API specification files plus the configuration (dictionary file path, inline dictionary, or annotation file path) that should be used for just this file, overriding any global options.

    For example:

    ``` json
    "SwaggerSpecConfig": [
        {
            "SpecFilePath": "swagger1.json",
            "DictionaryFilePath": "dict1.json"
        },
        {
            "SpecFilePath": "swagger2.json",
            "AnnotationFilePath": "swagger2_annotations.json",
            "Dictionary": {
                    "restler_custom_payload": {
                        "api-version": ["2020-10-27"]
                	}
            }
        }
    ]
    ```



* *GrammarInputFilePath* is the path to the RESTler json grammar.  A grammar previously generated from the Swagger specification may be modified and specified as input to the same compilation, and the corresponding Python grammar will be generated (this avoids maintaining the Python grammar directly).  This option may be used for targeted changes to the grammar which cannot be made by other configuration options.

* *CustomDictionaryFilePath* is the path to a fuzzing dictionary in JSON format.  The schema of the fuzzing dictionary and how to use it is described in [Fuzzing Dictionary](FuzzingDictionary.md).

    *Note*: a new dictionary, possibly with some changes, is generated during compilation in its output sub-directory.  You must make any further changes in your original version, or by making a copy of the generated dictionary.  If you make modifications in the generated version, they will be over-written the next time you run the compiler.

* *AnnotationFilePath* is the path to the RESTler annotations in JSON format.  The schema of the annotation file and how to use it is described in [Annotations](Annotations.md).

* *UseBodyExamples* specifies that the examples referenced in the Swagger specification (e.g., via the *x-ms-examples* attribute) for body parameters should be used.  If there are no examples specified, no error will be issued, and the schema alone will be used to generate the request payload.

* *UseQueryExamples* has the same behavior as UseBodyExamples, but for query parameter examples.

* *UseHeaderExamples* has the same behavior as UseBodyExamples, but for header parameter examples.

* *UsePathExamples* has the same behavior as UseBodyExamples, but for path parameter examples.

* *ResolveBodyDependencies* specifies that the body of a request should be analyzed for producer-consumer dependencies and for values specified in the fuzzing dictionary.  When set to 'false', the example payload or schema is used as-is, i.e. all properties are left untouched (either set to example values or fuzzable types).  When set to 'true', all properties of the body parameters (including nested properties) will be analyzed and the appropriate references (per dictionary, annotations, and inferred producer-consumer relationships) will be set in the grammar.  For example, if the fuzzing dictionary contains a custom 'api-version', this value will be used for this property instead of the value in the example payload.

* *ResolveQueryDependencies* has the same behavior as ResolveBodyDependencies, but for query parameters.

* *ResolveHeaderDependencies* has the same behavior as ResolveBodyDependencies, but for header parameters.

* *EngineSettingsFilePath* is the path to the RESTler engine settings file.  This argument is optional.  If specified, the contents of the engine settings may be updated during compilation, and the updated version is placed in the output directory.  This updated version should be used when fuzzing.

* *DiscoverExamples* If true, any examples found in the Swagger specification are
copied to a local directory, which can be configured through the *ExamplesDirectory*
setting (see below).  If the examples directory is not specified, a new sub-directory named
'examples' is created in the output directory.  If true, an examples metadata
file named ```examples.json``` will also be generated in the examples directory.
This file can be augmented with additional examples, and passed as an input to the
compilation using the *ExampleConfigFilePath* parameter (see below).

* *ExampleConfigFilePath* is the path to the file containing metadata about example parameter payloads.  See [Examples](Examples.md) for a description of the file format.
If this setting is not specified, and *DiscoverExamples* is set to ```false```,
the compiler looks for a default file named ```examples.json``` in the specified examples
directory.  If *DiscoverExamples* is false, every time an example is used
in the Swagger file, RESTler will first look for it in metadata,
and, if found, the externally specified example will override the example from the specification.

    See [Examples](Examples.md) for a description of the file format.
If this setting is not specified, and *DiscoverExamples* is set to ```false```,
the compiler looks for a default file named ```examples.json``` in the specified examples
directory.  If *DiscoverExamples* is false, every time an example is used
in the Swagger file, RESTler will first look for it in metadata,
and, if found, the externally specified example will override the example from the specification.


* *ExampleConfigFiles* is a setting that allows specifying several example config files
(files in which example parameter payload metadata is located), plus additional settings.
The currently supported settings are:
```
  "ExampleConfigFiles": [
    {
      "filePath": "C:\\examples_1.json",
      "exactCopy": false
    },
    {
      "filePath": "C:\\examples_2.json",
      "exactCopy": true
    },
  ]
```

- ```filePath``` is the path to the file containing metadata about example parameter payloads
- ```exactCopy``` specifies whether the example values should be merged with the schema and dictionary.  ```exactCopy``` is ```false``` by default.  When set to ```true```, constants from the example will be taken and override any other possible value (for example, custom payloads from the dictionary will not be used).  Note: parameters that are not in the specification but appear in the example are ignored.

* *UseAllExamplePayloads* When set to ```true```, all available example payloads are used (currently, both
the ones referenced in the specification and the ones
specified by the user in one or more example config files). ```False``` by default (the user-specified examples override
the ones from the specification).

* *ExamplesDirectory* is the directory where the compiler will copy example payloads
found in the Swagger file if *DiscoverExamples* is set to ```true```.
If *DiscoverExamples* is set to ```false```, RESTler tries to use examples in the
metadata file configured in *ExampleConfigFilePath*.  If *ExampleConfigFilePath* is not set,
then RESTler checks whether a file with the same name is present in the *ExamplesDirectory*,
and, if it is found, uses this local file instead of the file referenced in the specification.
This directory allows first discovering examples, then updating the local copy of the examples
with different values and maintaining them separately from the Swagger file.
The recommended way to use the updated examples in the compilation is to set *DiscoverExamples* to
```false``` and *ExampleConfigFilePath* to the generated ```examples.json``` in this directory.

* *DataFuzzing* True by default. When true, the compiler performs extra steps to enable data fuzzing. This parameter is true by default, and should only be set to false if you intend to disable the payload body checker.
* *AllowGetProducers* False by default.  By default, RESTler only assigns producer-consumer dependencies where the producer is a POST or PUT method (which will be used to create the resource).  When this option is set to true, the compiler will also allow resources returned from GET requests to be the producer.  Note: any endpoint+method specified in an annotation will be used as-is, regardless of this parameter, i.e., setting this parameter is not needed if explicit annotations are being used for dependencies involving GET producers.
* *ReadOnlyFuzz* False by default.  When true, only try to cover all the GET requests.  Others will be omitted from the grammar, unless they are required to execute the GET request (in which case they will be fuzzed too).
* *ApiNamingConvention* The naming convention of parameter names and properties
in the API specification.  This setting is optional, not set by default.  RESTler producer-consumer dependencies supports
several common conventions, and by default will try to infer the convention.  If several naming conventions are present, use the default.  However, if a single naming
convention is expected in the API spec, it may be preferable to set this parameter.  In particular, this may
catch consistency bugs in the specification because producer-consumer dependencies will not be inferred.  The supported values are:

    ```
    CamelCase
    PascalCase
    HyphenSeparator
    UnderscoreSeparator
    ```
* *TrackFuzzedParameterNames* False by default.  When true, every fuzzable primitive will
include an additional parameter `param_name` which is the name of the property or
parameter being fuzzed.  These will be used to capture fuzzed parameters in ```tracked_parameters``` in the spec coverage file.

* *JsonPropertyMaxDepth* is the maximum depth for Json properties in the schema to test.
Any properties exceeding this depth are removed.  There is no maximum by default.

* *IncludeOptionalParameters* True by default.  When false, RESTler will only pass required parameters when trying to successfully exercise each request.  The full schema including optional parameters is always included in the json grammar, so optional parameters will still be fuzzed by the payload body checker and available to test with ```test_combinations_settings``` when this option is set to false.
