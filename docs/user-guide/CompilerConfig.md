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

* *ResolveBodyDependencies* specifies that the body of a request should be analyzed for producer-consumer dependencies and for values specified in the fuzzing dictionary.  When set to 'false', the example payload or schema is used as-is, i.e. all properties are left untouched (either set to example values or fuzzable types).  When set to 'true', all properties of the body parameters (including nested properties) will be analyzed and the appropriate references (per dictionary, annotations, and inferred producer-consumer relationships) will be set in the grammar.  For example, if the fuzzing dictionary contains a custom 'api-version', this value will be used for this property instead of the value in the example payload.

* *ResolveQueryDependencies* has the same behavior as ResolveBodyDependencies, but for query parameters.

* *EngineSettingsFilePath* is the path to the RESTler engine settings file.  This argument is optional.  If specified, the contents of the engine settings may be updated during compilation, and the updated version is placed in the output directory.  This updated version should be used when fuzzing.

* *ExamplesDirectory* is the directory where the compiler should look for examples for query or body parameters. If *DiscoverExamples* (see below) is true, any examples found from Swagger references will be copied to this directory.  If *DiscoverExamples* is false, every time an example is used in the Swagger file, RESTler will first look for it in this directory.  This allows first discovering, then updating the examples to set your own values, and maintaining them separately from the Swagger file.


* *DiscoverExamples* If true, any examples found in the Swagger specification are copied to the *ExamplesDirectory* specified above.  If not specified, a new sub-directory named 'examples' is created in the output directory.
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