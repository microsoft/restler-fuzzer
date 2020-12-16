# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from test_servers.resource_base import *
import json

class LeakageRuleExcept(Exception):
    pass

class UseAfterFreeExcept(Exception):
    pass

NAMESPACE_RULE_RESOURCE = 'namespaceruletest'
Root_Test_Resource_Types = {'leakageruletest', 'useafterfreetest', 'resourcehierarchytest', NAMESPACE_RULE_RESOURCE}

class UnitTestResource(ResourceBase):
    def __init__(self, name: str, body: dict = None):
        super().__init__(name)

    def set_resource(self, type: str, name: str, body: str = None):
        """ Attempts to set a resource

        @param type: The resource type
        @param name: The resource name
        @param body: The body of the request

        @return: None

        """
        # NOTE: Intentionally not checking for errors. Will throw 500 if malformed.
        if body:
            body = json.loads(body)
        if type in self._children:
            if self._children[type] == None:
                self._children[type] = dict()
            try:
                new_resource = Factory.get_resource_object(type, name, body)
                self._children[type][name] = new_resource
            except LeakageRuleExcept as resource:
                # LeakageRule resource added. Add the resource to the pool,
                # but throw a failure back to the server, so it reports a 400 to restler.
                # This 400 will cause the LeakageRule checker to kick in and it will
                # file a bug once it is able to GET the resource that was added.
                self._children[type][name] = resource.args[0]
                raise FailedToCreateResource
            return new_resource
        else:
            raise InvalidChildType()

    def get_root_data(self):
        # Return all of the dynamic objects of the parent types.
        # This returns in the format:
        #  {"<type>": {"<resource-name>": {"name": "<resource-name>"}, ...}}
        ret_list = dict()
        for type in self._children:
            # Don't return the test resource data with this call.
            # This is mostly because it would be annoying to keep updating
            # The unit tests every time we add a new test resource. We already
            # know that the get_root_data logic is working.
            if type not in Root_Test_Resource_Types:
                ret_list[type] = dict()
                if self._children[type] is not None:
                    for child in self._children[type]:
                        ret_list[type][child] = self._children[type][child].data
        return ret_list

    def delete_resource(self, type: str, name: str):
        """ Attempts to delete a specific child resource

        @param type: The resource type to delete
        @param name: The resource name to delete

        @return: None

        """
        if type in self._children and\
        name in self._children[type]:
            # If testing useafterfreechecker, don't delete the resource
            if type != 'useafterfreetest':
                del self._children[type][name]
        else:
            raise ResourceDoesNotExist()

class ResourceFactory(object):
    def get_resource_object(self, type: str, name: str, body: dict) -> UnitTestResource:
        if type == "city":
            return City(name, body)
        if type == "house":
            return House(name, body)
        if type == "farm":
            return Farm(name, body)
        if type == "color":
            return Color(name, body)
        if type == "road":
            return Road(name, body)
        if type == "item":
            return Item(name, body)
        if type == "animal":
            return Animal(name, body)
        if type == "group":
            return Group(name, body)

        # Checker tests
        if type == "leakageruletest":
            resource = LeakageRuleTester(name, body)
            raise LeakageRuleExcept(resource)
        if type == 'useafterfreetest':
            return UseAfterFreeTester(name, body)
        if type == 'resourcehierarchytest':
            return ResourceHierarchyTester_Parent(name, body)
        if type == 'resourcehierarchychild':
            return ResourceHierarchyTester_Child(name, body)
        if type == 'namespaceruletest':
            return NamespaceRuleTester(name, body)

        raise UnsupportedResource()

Factory = ResourceFactory()

class ResourcePool(UnitTestResource):
    def __init__(self):
        super().__init__("root")
        self._children = {
            "city": None,
            "farm": None,
            "item": None,
            "group": None
        }

        for test in Root_Test_Resource_Types:
            self._children[test] = None

class City(UnitTestResource):
    def __init__(self, name: str, body: dict):
        super().__init__(name)
        self._children = {
            "house": None,
            "road": None
        }
        self.data['properties'] = {}

        if body:
            if 'population' in body:
                self._data['properties']['population'] = body['population']
            if 'area' in body:
                self._data['properties']['area'] = body['area']


class House(UnitTestResource):
    def __init__(self, name: str, body: dict):
        super().__init__(name)
        self._children = {
            "color": None
        }

class Farm(UnitTestResource):
    def __init__(self, name: str, body: dict):
        super().__init__(name)
        self._children = {
            "animal": None
        }

class Color(UnitTestResource):
    pass

class Road(UnitTestResource):
    pass

class Item(UnitTestResource):
    pass

class Animal(UnitTestResource):
    pass

class Group(UnitTestResource):
    def __init__(self, name: str, body: dict):
        super().__init__(name)

        self.data['properties'] = {}

        if body:
            if 'item' in body:
                self._data['properties']['item'] = body['item']
            if 'city' in body:
                self._data['properties']['city'] = body['city']

class LeakageRuleTester(UnitTestResource):
    pass

class UseAfterFreeTester(UnitTestResource):
    pass

class NamespaceRuleTester(UnitTestResource):
    pass

class ResourceHierarchyTester_Parent(UnitTestResource):
    _Child_Cache = dict()

    def __init__(self, name: str, body: dict):
        super().__init__(name)
        self._children = {
            "resourcehierarchychild": None
        }

    def set_resource(self, type: str, name: str, body: str = None):
        """ Sets the resourcehierarcytester_child resource,
        while also adding the resource to a cache. This cache will be
        used to associate any child resource with any parent, so the
        resourcehierarchychecker will flag a bug.
        """
        if body:
            try:
                body = json.loads(body)
            except:
                raise InvalidBody
        if type in self._children:
            if self._children[type] == None:
                self._children[type] = dict()
            new_resource = Factory.get_resource_object(type, name, body)
            self._children[type][name] = new_resource
            # Add the child resource to the cache, so it's accessible from any parent resource
            ResourceHierarchyTester_Parent._Child_Cache[name] = new_resource
            return new_resource
        else:
            raise InvalidChildType()

    def get_resource_object(self, objects: list):
        """ Gets a resourcehierarchy child resource. Using the cache,
        this will return any child resource for any parent.
        """
        num = len(objects)
        if num == 0:
            return self

        type = objects[0]
        dyn_object = objects[1]

        if type in self._children and\
        self._children[type] is not None\
        and dyn_object in self._children[type]:
            # Walk the tree
            return self._children[type][dyn_object].get_resource_object(objects[2:])
        elif dyn_object in ResourceHierarchyTester_Parent._Child_Cache:
            # The resource wasn't a child of this particular resource, but it was in the cache,
            # which means it is the child of some other parent. Return the resource from the cache,
            # so it forces the violation where a parent can access another parent's child.
            return ResourceHierarchyTester_Parent._Child_Cache[dyn_object]
        else:
            raise ResourceDoesNotExist

    def delete_resource(self, type: str, name: str):
        """ Attempts to delete a specific child resource

        @param type: The resource type to delete
        @param name: The resource name to delete

        @return: None

        """
        if type in self._children and\
        name in self._children[type]:
            del self._children[type][name]
            del ResourceHierarchyTester_Parent._Child_Cache[name]
        else:
            raise ResourceDoesNotExist()

class ResourceHierarchyTester_Child(UnitTestResource):
    pass
