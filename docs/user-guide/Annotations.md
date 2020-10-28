# RESTler annotations in Swagger files

RESTler allows the user to provide annotations with information about producer-consumer dependencies between requests.  This is helpful when RESTler cannot automatically infer such dependencies, which can happen for a variety of reasons (most often, because of very generic or inconsistent naming in the specification, or if the naming convention is not implemented in RESTler).

Annotations are supported either globally (apply to all requests) or locally (apply only to a single request).  They may be specified inline in the Swagger specification (preferred if generated from the code, to evolve with the API) or outside in a separate file (preferred when modifications to the Swagger/OpenAPI spec are not acceptable, or maintaining a separate file is easier in your specific workflow).

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

To provide local annotations inline in the Swagger/OpenAPI spec,
include the above block globally as follows (Note: only JSON is currently supported):

```json
{
  "swagger": "2.0",
  ...
  "x-restler-global-annotations": [
    {<annotation>},
    {<annotation>}
  ]
}
```


## Local annotations

Providing local annotations in a separate file is not currently supported.

To provide local annotations inline in the Swagger/OpenAPI spec, specify the above block in the request block inside the Swagger/OpenAPI document:

```json
{
    "swagger": "2.0",
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



## Annotation format

Below is an example annotation that includes all supported properties:

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

In some cases, the resource names in the above may be ambiguous, e.g. because several resources with the same name are present in the body of a request or response.  You may use the json pointer notation to specify the full path to the resource.  For example:

```json
{
    "producer_endpoint": "/api/zones/{zoneName}",
    "producer_method": "PUT",
    "producer_resource_name": "/accounts/[0]/zones/[0]/name",
    "consumer_param": "/accounts/[0]/zones/[0]/name"
}
```

