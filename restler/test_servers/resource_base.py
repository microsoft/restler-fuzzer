# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABCMeta, abstractmethod

class InvalidChildType(Exception):
    """ To be raised when a child type is invalid for the parent.
    Correct: /Parent/{ParentName-}/Child/{ChildName-}
    InvalidChildType: /Parent/{ParentName-}/NonChild/{NonChildName-}
    """
    pass

class UnsupportedResource(Exception):
    """ To be raised when an unsupported resource type is
    in a path.
    Correct: /ValidResource/{ValidResourceName-}
    UnsupportedResource: /InvalidResource/{InvalidResourceName-}
    """
    pass

class ResourceDoesNotExist(Exception):
    """ To be raised when a resource specified in a path
    does not exist.
    Correct: /ValidResource/{ValidResourceName-}
    ResourceDoesNotExist: /ValidResource/{InvalidResourceName-}
    """
    pass

class FailedToCreateResource(Exception):
    """ To be raised when a resource creation failed.
    Intended to be used primarily for testing the behavior of a failed resource.
    For instance, if body data is incorrect or a specific checker is being tested.
    """
    pass

class InvalidBody(Exception):
    """ To be raised when a request body is invalid or malformed.
    Example use is for a malformed body (invalid json).
    """
    pass

class ResourceBase:
    __metaclass__ = ABCMeta

    def __init__(self, name: str):
        self._data: dict = {
            "name": name
        }
        self._children: dict = {}

    @property
    def data(self):
        return self._data

    def __del__(self):
        self._children.clear()

    def add_resource(self, objects: list, body: str = None):
        """ Attempts to add a new resource

        @param objects: The list of dynamic object types and names that
                        were included in the endpoint. The format is:
                        type0/name0/type1/name1/...
        @param body: The request's body.

        @return: The resource that was set
        @rtype : ResourceBase

        """
        if len(objects) % 2 != 0:
            # objects length must be even number (type0/name0/type1/name1/...)
            raise UnsupportedResource()

        parent_type = objects[0]
        parent_name = objects[1]

        if parent_type not in self._children:
            # Not a valid child of this resource type
            raise UnsupportedResource()

        if len(objects) == 2:
            # Final resource in the endpoint, set it
            return self.set_resource(parent_type, parent_name, body)
        else:
            resource = self.get_resource_object(objects[:-2])
            return resource.set_resource(objects[-2], objects[-1], body)
        return resource

    @abstractmethod
    def set_resource(self, type: str, name: str, body: str = None):
        """ Attempts to set a specific resource.
        Must be initialized by each Resource subclass

        @param type: The resource type
        @param name: The resource name
        @param body: The request body.

        @return: The resource that was set
        @rtype : ResourceBase

        """
        pass

    def delete_resource(self, type: str, name: str):
        """ Attempts to delete a specific child resource

        @param type: The resource type to delete
        @param name: The resource name to delete

        @return: None

        """
        if type in self._children and\
        name in self._children[type]:
            del self._children[type][name]
        else:
            raise ResourceDoesNotExist()

    def get_resource_object(self, objects: list):
        """ Gets a ResourceBase object from a list of resources that
        represent the endpoint.

        @param objects: The list of dynamic object types and names that
                were included in the endpoint. The format is:
                type0/name0/type1/name1/...

        @return: The resource object at the end of the endpoint

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
        else:
            raise ResourceDoesNotExist

    def get_data(self, type: str = None) -> dict:
        """ Returns data from a specified resource or resource group

        @param type: The 'type' of the resource to get data from.
        @param name: The 'name' of the individual resource to get data from.
                     Note: If this is left as None, will return data from all
                     resources of the specified @type

        @return: The data from the resource or resource type
                 - If getting from a type/resource group, return all of
                 the dynamic object data of that type.
                 - If getting a resource, return all of it's data

        """
        if type:
            if type in self._children:
                # If just getting from a type, return dyn objects of this type
                ret_list = {type: dict()}
                if self._children[type] is not None:
                    for child in self._children[type]:
                        ret_list[type][child] = self._children[type][child].data
                return ret_list
            else:
                raise ResourceDoesNotExist
        else:
            return self.data

