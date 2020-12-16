# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from test_servers.test_server_base import *
from test_servers.unit_test_server.unit_test_resources import *
from test_servers.parsed_requests import *

import traceback

VALID_UNIT_TEST_TOKEN = 'valid_unit_test_token'

class UnitTestServer(TestServerBase):
    PRINT_DEBUG = False

    _resources: ResourcePool = ResourcePool()

    def __init__(self):
        super().__init__()

        self._methods: dict = {
            "GET": self._GET,
            "PUT": self._PUT,
            "DELETE": self._DELETE
        }

    def _reset_resources(self):
        """ Used to reset resources during unit testing of the server """
        UnitTestServer._resources = ResourcePool()

    def _test_print(self, message):
        if UnitTestServer.PRINT_DEBUG:
            print(message)

    def _authorization_valid(self, auth_token: str, dyn_objects: list) -> bool:
        """ Helper that checks for a valid authorization token.
        If this is a namespace rule test request, the authorization token will be ignored
        and True will always be returned.

        @param auth_token: The authorization token (could be None)
        @param dyn_objects: The list of dynamic objects
        @return: True if authorization is valid

        """
        if NAMESPACE_RULE_RESOURCE not in dyn_objects:
            if auth_token is not None and auth_token == VALID_UNIT_TEST_TOKEN:
                return True
            return False
        return True

    def parse_message(self, message):
        """ Parses a Request and its endpoint for dynamic objects

        Format of a request's endpoint should be as follows:
        /<dyn_object_type1>/<dyn_object_name1>/<dyn_object_type2>/<dyn_object_name2>...
        Example:
        /city/Seattle/house/house123

        In the above request:
            - Each dynamic object type/name is treated like a key/value pair. In the example above,
            city is the key and Seattle is the value, so a City resource is created of the name Seattle.
            This is the same for house->house123. Additionally, the child resources (house123 in the example),
            are directly tied to their parent resources (Seattle in the example). What this means is that
            house123 will be added to the Seattle resource's collection of children. The house123 resource
            cannot be accessed via some other parent or on its own.

            Note that this assumes a leading '/' in the endpoint.
        """
        from engine.transport_layer.messaging import UTF8
        message = message.decode(UTF8)
        self._test_print(f"Test server received message: {message}")
        try:
            if message:
                request = ParsedRequest(message)
                self._test_print(f"Method: {request.method}")
            else:
                self._response = self._400("Request was empty")
                return

            if request.method in self._methods:
                self._methods[request.method](request)
            else:
                self._response = self._405(request.method)
        except UnknownRequest:
            self._response = self._400("Unknown request")
        except Exception as err:
            traceback.print_exc()
            self._response = self._500(f"Error detected in restler Engine! {err!s}")

    def _get_dyn_objects(self, endpoint) -> list:
        """ Splits an endpoint string into a list of dynamic objects.
            The format should be:
            [type0, name0, type1, name1, ...]

            This function expects a leading '/'
        """
        try:
            vals = endpoint.split('/')
            return vals[1:]
        except:
            raise UnknownRequest()

    def _GET(self, request: ParsedRequest):
        try:
            dyn_objects = self._get_dyn_objects(request.endpoint)
            if not self._authorization_valid(request.authorization_token, dyn_objects):
                self._response = self._403()
                return
            num = len(dyn_objects)
            if dyn_objects[0] == '':
                # Getting only the root data
                data = UnitTestServer._resources.get_root_data()
            elif num % 2 == 1:
                # Getting data from a 'type' only
                # A common pattern for endpoints follows this example:
                # /.../containerType/{containerName}
                resource = UnitTestServer._resources.get_resource_object(dyn_objects[:-1])
                data = resource.get_data(dyn_objects[-1])
            else:
                # Getting actual resource data from a resource name
                resource = UnitTestServer._resources.get_resource_object(dyn_objects)
                data = resource.get_data()
            self._response = self._200(data)
        except ResourceDoesNotExist as resource:
            self._response = self._404(resource)
        except Exception as error:
            self._response = self._500(str(error))

    def _PUT(self, request: ParsedRequest):
        try:
            dyn_objects = self._get_dyn_objects(request.endpoint)
            if not self._authorization_valid(request.authorization_token, dyn_objects):
                self._response = self._403()
                return
            resource = UnitTestServer._resources.add_resource(dyn_objects, request.body)
            self._response = self._201(resource.data)
        except ResourceDoesNotExist as resource:
            self._response = self._404(resource)
        except UnsupportedResource as resource:
            self._response = self._400(resource)
        except InvalidChildType as resource:
            self._response = self._400(resource)
        except FailedToCreateResource as resource:
            self._response = self._400(resource)
        except InvalidBody:
            self._response = self._400(request.body)
        except Exception as error:
            self._response = self._500(str(error))

    def _DELETE(self, request: ParsedRequest):
        try:
            dyn_objects = self._get_dyn_objects(request.endpoint)
            if not self._authorization_valid(request.authorization_token, dyn_objects):
                self._response = self._403()
                return
            num = len(dyn_objects)
            if num % 2 != 0:
                # Must be even number of dynamic objects as we can only delete
                # a specific object and not an entire 'type'
                self._response = self._400(f"Invalid resource: {dyn_objects[-1]}")
                return
            if num == 2:
                # deleting a first level resource, so just delete from root
                UnitTestServer._resources.delete_resource(dyn_objects[0], dyn_objects[1])
            else:
                # deleting deeper into the tree, so get the parent of a dynamic object
                resource = UnitTestServer._resources.get_resource_object(dyn_objects[:-2])
                resource.delete_resource(dyn_objects[-2], dyn_objects[-1])
            self._response = self._202(dyn_objects[-1])
        except ResourceDoesNotExist as resource:
            self._response = self._404(resource)
        except Exception as error:
            self._response = self._500(str(error))
