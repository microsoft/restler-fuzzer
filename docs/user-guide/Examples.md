# Using Payload Examples in RESTler

A Swagger/OpenAPI specification may contain example payload values for
request parameters and responses.  Such examples are frequently used
to enhance user documentation with current example payloads that can
be used to run sample requests against the live service.  The examples can be either inlined
in the specification or provided in a separate file, referenced from
the specification.

## Supported RESTler use cases

RESTler supports the following use cases for example payloads:

1. **Help RESTler successfully execute a request** If RESTler finds an example payload, it will use it to execute the request, instead of using a generated payload based on the full schema specified in the Swagger file.   This can help the user specify valid values for the entire payload, which RESTler can use to successfully execute a request.  This is often necessary when there are dependent request parameters, which is not expressed in the Swagger/OpenAPI spec, such as an enum value query parameter that can only be used with a subset of the body parameters.

   *Warning*: the first example payload found will be the one that is used as the primary payload for the request, instead of the schema.

2. **Help RESTler fuzz the body payloads more effectively**  If RESTler finds one or more example payloads, it will use the values found to fuzz json bodies via the payload body checker.

   *Warning*: this use case is currently intended to support a small number of examples.  Providing many examples may cause issues generating the RESTler grammar, since they are embedded in the grammar.

RESTler does not currently support inferring the payload schema based on examples.  Moreover, it requires that the example-provided parameters match the declared schema, and will discard the non-matching ones.  This means that if your Swagger/OpenAPI specification is missing a schema for the parameters or response (e.g. an "object" for both), examples cannot be used to fix this quickly by overriding the specification.

RESTler only supports parameter payload examples.  It does not currently use response payload examples.

## Specifying examples inline in the specification

A Swagger/OpenAPI specification supports specifying examples for individual parameters inline, or an external file specifying the entire payload.  RESTler currently supports the latter, declared as follows:

``` json
{
    "Examples": {
        "First example": {
            "$ref":  "./examples/first.json"
        },
        "Second example": {
            "$ref":  "./examples/second.json"
        }
    }
}
```

Both the attribute ```Examples``` and ```x-ms-examples``` are supported.

## Specifying examples in a separate file
For cases when  it is desirable to augment the existing examples, use the *DiscoverExamples* and *ExamplesDirectory* compilation parameters.  When *DiscoverExamples* is ```true```, all of the examples found in the OpenAPI/Swagger specification are copied to a separate folder.
When specifying example payloads through an example file, set *DiscoverExamples* to ```false```.

The format of the example file is as follows.  Note that either an external file or inline example can be specified.  Inline examples are useful for initial setup/debugging, but we recommend using external files to maintain examples separately for different requests.

For specifying example body payloads, it is recommended to use the special keyword ```__body__```.
This special property name will cause RESTler to assign this property value to the body,
ignoring the name of the body parameter in the schema.  Because the body parameter name
is not part of the actual body payload, this property name makes it more clear and less error prone
to see where the body is specified in examples.

```json

{
    "paths": {
        "/blog/posts": {
            "post": {
                "1": {
                    "parameters": {
                        "payload": {
                        "body": "first blog",
                        "tags": ["spring", "outdoors"]
                        }
                    }
                },
                "2": "c:\\secondExample.json",
                "3": {
                    "parameters": {
                        "__body__": {}
                    }
                }
            }
        }
    }
}

```

When *DiscoverExamples* is ```true```, a file named ```examples.json``` will be output in the compilation output directory with all of the examples discovered.

***Warning***: the compilation directory, including examples, is overwritten on every compilation.  By default, if the *DiscoverExamples* compilation parameter is set to ```true```, but an *ExamplesDirectory* is not set, RESTler will copy of all of the examples into an *examples* sub-directory in the compilation directory.  Once you have discovered examples, move them to a different directory to modify them, and set the *ExamplesDirectory* to that directory on the next compilation (and the *DiscoverExamples* parameter to ```false``` to use this copy of examples.)

## Known issues

### First example only used in main search algorithm

When example payload is found, RESTler will use it to try executing the request, instead of the payload generated by the schema.  ***Known issue***:  Only the *first* example listed in the OpenAPI/Swagger or external example file will be used, and if it fails, the other examples will not be tried.   This means you must make sure that the first example in the list of examples will cause a successful (```20*``` ) status code.  The other examples will also be executed by RESTler but in a separate pass (via the *examples checker*), but they will not be used in full search mode.  This means that if there are ```3``` examples for a request ```POST /api/database```, which create ```3``` different types of databases, a subsequent request ```PUT /api/databases/{databaseId}/backup```, the ```backup``` request will only be executed once, for the first type of database (in the order listed in the examples file.)
