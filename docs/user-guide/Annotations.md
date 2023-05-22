# RESTler annotations

RESTler allows the user to provide annotations with information about producer-consumer dependencies between requests.  This is helpful when RESTler cannot automatically infer such dependencies, which can happen for a variety of reasons (most often, because of very generic or inconsistent naming in the specification, or if the naming convention is not implemented in RESTler).

RESTLer can also use dependency information expressed in OpenAPI v3 links.  See [Using OpenAPI v3 links to define dependencies](Links.md) for more information.

## Annotation format

Annotations are supported either globally (apply to all requests) or locally (apply only to a single request).  They may be specified inline in the OpenAPI definition (preferred if generated from the code, to evolve with the API) or outside in a separate file,
which can be specified in the [Compiler config](CompilerConfig.md).  The latter is preferred when modifications to the OpenAPI file are not acceptable, or maintaining a separate file is easier in your specific workflow.

## Supported types of dependencies
RESTler currently supports the following types of producer-consumer dependencies:
1. Between a response property and a request parameter.
For example: request ```POST /A``` returns property "id", and request ```GET /A/{aId}``` specifies this ID in the path.

2. Between two request parameters in different requests, where one of these is a ```custom_payload_uuid_suffix```.
For example: ```PUT /A/{aId}``` creates a resource with ID ```aId```, and ```GET /A/{AId}``` must use this ID, but the ID is not returned in the response.

The annotation format for this annotation is the same as for annotations for producers that are response properties (as in (1)). RESTler will first look for the property name in the response, and if it does not find it will create this new kind of "input producer". The annotation does not explicitly allow to specify whether the ID should be extracted out of the response or not.

3. Between two properties in the body.
For example: "request ```PUT /A/{aId}``` has properties in the body that also need to refer to ```aId```, whose value is unique for each request invocation (via ```restler_custom_payload_uuid4_suffix```)

4. Between two requests.  These ordering constraints may be specified as global annotations.

Annotations are only supported for dependencies of type (1), (2) and (4) above.


## Global annotations

When provided in a separate file (e.g. annotations.json), the file contents should be:

```json
{
    "x-restler-global-annotations": [
       {<annotation>},
       {<annotation>}
    ]
}
```

To provide local annotations inline in the OpenAPI file,
include the above block globally as follows (Note: only JSON is currently supported):

```json
{
  "openapi": "3.0.0",
  ...
  "x-restler-global-annotations": [
    {<annotation>},
    {<annotation>}
  ]
}
```


## Local annotations

Providing local annotations in a separate file is not currently supported.

To provide local annotations inline in the OpenAPI file, specify the above block in the request block inside the OpenAPI document:

```json
{
    "openapi": "3.0.0",
    "paths": {
        "/blog/posts/{id}": {
            "get": {
                "x-restler-annotations": [
                    {
                        "producer_resource_name": "id",
                        "producer_method": "POST",
                        "consumer_param": "id",
                        "producer_endpoint": "/blog/posts"
                    }
                ]
            }
        }
    }
}
```

The `consumer_endpoint` and `consumer_method` are implied by the request block in which the annotation is specified.

## Annotation format

The following information can be supplied in a annotation:

- `producer_endpoint`: the "path" of the operation that "produces" a value for the consuming operation
- `producer_method`: the HTTP method of the producer operation
- `producer_resource_name`: the name of the value produced. This can be the name of a property in the response body, the name of a response header, or the name of a path or query parameter in the request.
- `consumer_param`: the name of the path, query, or header parameter, or the name of a property in the request body consumed by the consumer operation.
- `consumer_endpoint`: the "path" of the operation that "consumes" the value produced by the producer operation.
- `consumer_method`: the HTTP method of the consumer operation.
- `except`: a list of consumers that should not use the producer in the annotation.
- `description`: a description of the dependency.

The `producer_endpoint` and `producer_method` are required. The `consumer_endpoint` and `consumer_method` are optional in global annotations, and are implied in local annotations.  If the consumer endpoint and method are not specified in a global annotation, every consumer request type that contains a matching `consumer_param` will have the annotation applied to it.  The `except` property is only meaningful in global annotations.

Below is an example annotation.  The ```except``` property may be either an object or an array with a list of except consumers.

```json
{
    "producer_endpoint": "/api/zones/{zoneName}",
    "producer_method": "PUT",
    "producer_resource_name": "name",
    "consumer_param": "zoneName",
    "except": {
        "consumer_endpoint": "/api/directions/{zoneName}",
        "consumer_method": "GET"
    }
}
```

This annotation specifies how resources of type "zone" are produced by this API: a "zoneName" is specified with a PUT request (see *producer_method*) executed on the specified *producer_endpoint* and, if successful, the name of the resource created is returned in the "name" field in the response (see *producer_resource_name*). The *except* part of the annotation specifies that the endpoint and method in the except clause should not use the producer in the annotation.  The *consumer_param* type above is for the consumer. In this case, the consumer request value of "zoneName" will consume the value from the response of the producer.

In some cases, the resource names in the above may be ambiguous, e.g. because several resources with the same name are present in the body of a request or response.  You may use [JSON pointer][] notation to specify the full path to the resource.  For example:

[JSON pointer]: https://tools.ietf.org/html/rfc6901

```json
{
    "producer_endpoint": "/api/zones/{zoneName}",
    "producer_method": "PUT",
    "producer_resource_name": "/accounts/[0]/zones/[0]/name",
    "consumer_param": "/accounts/[0]/zones/[0]/name"
}
```

An ordering constraint may also be specified, which only includes the request type,
without any resource names.  For example:

```json
{
    "producer_endpoint": "/resource/{resourceId}/start",
    "producer_method": "POST",
    "consumer_endpoint": "/resource/{resourceId}/stop",
    "consumer_method": "POST",
}
```
