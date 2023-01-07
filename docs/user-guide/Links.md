# Using OpenAPI v3 links to define dependencies

The OpenAPI v3 specification defines [link objects][] that can be used to define dependencies between operations.
Restler will use links when present in the API definition to generate dependencies between operations.

[link objects]: https://github.com/OAI/OpenAPI-Specification/blob/3.0.3/versions/3.0.3.md#link-object

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