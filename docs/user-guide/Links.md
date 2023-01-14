# Using OpenAPI v3 links to define dependencies

The OpenAPI v3 specification defines [link objects][] that can be used to define dependencies between operations.
RESTler will use links when present in the API definition to generate dependencies between operations.

[link objects]: https://github.com/OAI/OpenAPI-Specification/blob/3.0.3/versions/3.0.3.md#link-object

OpenAPI links provide a subset of the functionality of RESTler annotations. Links can specify that
a value from the request or response of one operation (the "producer") can be used as the value
of a parameter in another operation (the "consumer").
The value from the producer can come from a property in the response body, a response header,
or a path or query parameter in the request.
Links cannot specify that the value from the producer can be used in the request body of the consumer.
The link is defined in the response of the producer operation, in contrast to RESTler local annotations,
which are defined in the consumer operation.

RESTler currently supports links that use the `operationId` field to specify the target operation
rather than the `operationRef` field.
The current implementation also only processes the first parameter in the link object, since links that
specify multiple parameters are expected to be rare.

## Example

A service that implements conditional requests may return an `ETag` header in the response to a GET request.
The value of the `Etag` header can be specified in the `If-Match` header of a subsequent PATCH request
to update the resource.

This dependency can be expressed in an OpenAPI definition by including a "links" object in the response
of the GET operation as follows:

```yaml
  responses:
    '200':
      description: The request has succeeded.
      headers:
      etag:
          required: true
          schema:
          type: string
      content:
      application/json:
          schema:
          $ref: '#/components/schemas/Widget'
      links:
        WidgetUpdate:
          description: Link to If-Match parameter
          operationId: Widgets_update
          parameters:
            header.if-match: $response.header.etag
```