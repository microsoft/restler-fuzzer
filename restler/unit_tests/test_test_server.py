# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from test_servers.test_socket import *
from test_servers.unit_test_server.unit_test_resources import *
from test_servers.unit_test_server.unit_test_server import *
from engine.transport_layer.response import HttpResponse
from engine.transport_layer.messaging import UTF8

class TestServerTest(unittest.TestCase):
    def test_resource_pool(self):
        pool = ResourcePool()

        self.assertEqual("root", pool.data["name"])
        self.assertIsNone(pool._children["city"])
        self.assertIsNone(pool._children["farm"])
        self.assertIsNone(pool._children["item"])

        with self.assertRaises(Exception):
            pool._children["house"]

        # Add a city
        pool.add_resource(["city", "city-123"], body='{"population": 5000}')
        # Check get city objects
        data = pool.get_data("city")
        self.assertEqual("city-123", data['city']['city-123']['name'])
        # Check get specific city
        data = pool.get_resource_object(['city', 'city-123']).get_data()
        self.assertEqual('city-123', data['name'])
        self.assertEqual(5000, data['properties']['population'])

        # Add additional city
        pool.add_resource(["city", "city-456"])
        data = pool.get_data("city")
        # Check new city exists
        self.assertEqual("city-456", data['city']['city-456']['name'])
        # Check old city still exists
        self.assertEqual("city-123", data['city']['city-123']['name'])

        # Add house to a city
        pool.add_resource(["city", "city-123", "house", "house-8"])
        # Check list of houses of this city
        resource = pool.get_resource_object(["city", "city-123"])
        data = resource.get_data('house')
        self.assertEqual("house-8", data['house']['house-8']['name'])
        # Check specific house in the city
        resource = pool.get_resource_object(['city', 'city-123', 'house', 'house-8'])
        data = resource.get_data()
        self.assertEqual('house-8', data['name'])

        # Add color to a house
        pool.add_resource(['city', 'city-123', 'house', 'house-8', 'color', 'color-red'])
        # Check list of colors of the house
        resource = pool.get_resource_object(['city', 'city-123', 'house', 'house-8'])
        data = resource.get_data('color')
        self.assertEqual("color-red", data['color']['color-red']['name'])
        # Check specific color of the house
        resource = pool.get_resource_object(['city', 'city-123', 'house', 'house-8', 'color', 'color-red'])
        data = resource.get_data()
        self.assertEqual('color-red', data['name'])

        data = pool.get_root_data()
        test_dict = {'city' :
            {'city-123': {'name': 'city-123', 'properties': {'population': 5000}},
            'city-456': {'name': 'city-456', 'properties': {}}},
            'farm': {}, 'item': {}, 'group': {}
            }
        self.assertDictEqual(test_dict, data)

        with self.assertRaises(ResourceDoesNotExist):
            pool.get_resource_object(['city', 'city-999'])
            pool.get_data('country')
            pool.get_resource_object(['city', 'city-123', 'house', 'house-5'])
            pool.get_resource_object(['city', 'city-456', 'house', 'house-8'])
            pool.add_resource(['city', 'city-456', 'house', 'house-123'])

        with self.assertRaises(InvalidChildType):
            pool.add_resource(['city', 'city-123', 'farm', 'farm-123'])

        with self.assertRaises(InvalidChildType):
            pool.set_resource('road', 'road123')

        pool.delete_resource('city', 'city-123')
        data = pool.get_root_data()

        test_dict = {'city' :
            {'city-456': {'name': 'city-456', 'properties': {}}},
            'farm': {}, 'item': {}, 'group': {}
            }
        self.assertDictEqual(test_dict, data)

        with self.assertRaises(ResourceDoesNotExist):
            pool.delete_resource('city', 'city-123')

        with self.assertRaises(ResourceDoesNotExist):
            pool.get_resource_object(['city', 'city-123'])
            pool.add_resource(['city', 'city-123', 'house', 'house-5'])

        # Test leakage rule checker
        with self.assertRaises(FailedToCreateResource):
            pool.add_resource(['leakageruletest', 'test-123'])
        resource = pool.get_resource_object(['leakageruletest', 'test-123'])
        data = resource.get_data()
        self.assertEqual('test-123', data['name'])

        # Test resource hierarchy checker
        pool.add_resource(['resourcehierarchytest', 'resourceparent'])
        resource = pool.get_resource_object(['resourcehierarchytest', 'resourceparent'])
        data = resource.get_data()
        self.assertEqual('resourceparent', data['name'])
        pool.add_resource(['resourcehierarchytest', 'resourceparent', 'resourcehierarchychild', 'resourcechild'])
        resource = pool.get_resource_object(['resourcehierarchytest', 'resourceparent', 'resourcehierarchychild', 'resourcechild'])
        data = resource.get_data()
        self.assertEqual('resourcechild', data['name'])
        pool.add_resource(['resourcehierarchytest', 'resourceparent2'])
        resource = pool.get_resource_object(['resourcehierarchytest', 'resourceparent2'])
        data = resource.get_data()
        self.assertEqual('resourceparent2', data['name'])
        resource = pool.get_resource_object(['resourcehierarchytest', 'resourceparent2', 'resourcehierarchychild', 'resourcechild'])
        data = resource.get_data()
        self.assertEqual('resourcechild', data['name'])

    def test_get(self):
        sock = TestSocket('unit_test')

        req = f"GET /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\nUser-Agent: restler/3.0.0.0\r\n\r\n"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('200', sock.recv().status_code)

        req = f"GET /city HTTP/1.1\r\nContent-Length: 0\r\nUser-Agent: restler/3.0.0.0\r\n\r\n"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('403', sock.recv().status_code)

        req = f'GET /city/fuzzstring HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertEqual('404', sock.recv().status_code)

        sock._server._reset_resources()

    def test_put(self):
        sock = TestSocket('unit_test')

        req = f"PUT /city/city-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('201', sock.recv().status_code)

        req = f'GET /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('city-123' in sock.recv().body)

        req = f"PUT /city/city-124 HTTP/1.1\r\nContent-Length: 0\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('403', sock.recv().status_code)

        req = f'GET /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertFalse('city-124' in sock.recv().body)

        req = f'GET /city/city-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('city-123' in sock.recv().body)

        req = f"PUT /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('400', sock.recv().status_code)

        body = {"population": 5000, "area": 2000}
        bodystr = json.dumps(body)
        req = f"PUT /city/city-999 HTTP/1.1\r\nContent-Length: {len(bodystr)}\r\nAuthorization: valid_unit_test_token\r\n\r\n{bodystr}"
        sock.sendall(req.encode(UTF8))
        res = sock.recv()
        resbody = json.loads(res.body)
        self.assertEqual('201', res.status_code)
        self.assertTrue('population' in resbody['properties'])
        self.assertTrue('area' in resbody['properties'])
        self.assertEqual(5000, resbody['properties']['population'])
        self.assertEqual(2000, resbody['properties']['area'])

        req = f"PUT /house/house-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('400', sock.recv().status_code)

        req = f"PUT /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('400', sock.recv().status_code)

        req = f"PUT /city/city-123/house/house-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('201', sock.recv().status_code)

        req = f'GET /city/city-123/house HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('house-123' in sock.recv().body)

        req = f'GET / HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        res = json.loads(sock.recv().body)
        self.assertTrue('city' in res)
        self.assertTrue('city-123' in res['city'])
        self.assertTrue('farm' in res)
        self.assertTrue(not res['farm'])
        self.assertTrue('item' in res)
        self.assertTrue(not res['item'])

        sock._server._reset_resources()

    def test_delete(self):
        sock = TestSocket('unit_test')

        req = f"PUT /city/city-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('201', sock.recv().status_code)

        req = f"PUT /city/city-123/house/house-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('201', sock.recv().status_code)

        req = f"PUT /city/city-123/house/house-123/color/red-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('201', sock.recv().status_code)

        req = f'GET /city/city-123/house/house-123/color/red-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('red-123' in sock.recv().body)

        req = f'DELETE /city/city-123/house/house-123/color/red-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertEqual('202', sock.recv().status_code)

        req = f'GET /city/city-123/house/house-123/color/red-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertFalse('red-123' in sock.recv().body)

        req = f"PUT /city/city-123/house/house-123/color/red-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('201', sock.recv().status_code)

        req = f'GET /city/city-123/house/house-123/color/red-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('red-123' in sock.recv().body)

        req = f'DELETE /city/city-123/house/house-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertEqual('202', sock.recv().status_code)

        req = f'GET /city/city-123/house/house-123/color/red-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertFalse('red-123' in sock.recv().body)

        req = f'GET /city/city-123/house/house-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertFalse('house-123' in sock.recv().body)

        req = f'GET /city/city-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('city-123' in sock.recv().body)

        req = f'DELETE /city/city-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertEqual('202', sock.recv().status_code)

        req = f'GET /city/city-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertFalse('city-123' in sock.recv().body)

        req = f'GET /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertFalse('city-123' in sock.recv().body)

        req = f'GET / HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        res = json.loads(sock.recv().body)
        self.assertTrue('city' in res)
        self.assertTrue('farm' in res)
        self.assertTrue('item' in res)
        self.assertTrue(not res['city'])
        self.assertTrue(not res['farm'])
        self.assertTrue(not res['item'])

        req = f'DELETE /city/city-123 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertEqual('404', sock.recv().status_code)

        req = f'DELETE /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertEqual('400', sock.recv().status_code)

        req = f"PUT /city/city-124 HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n{{}}"
        sock.sendall(req.encode(UTF8))
        self.assertEqual('201', sock.recv().status_code)

        req = f'GET /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('city-124' in sock.recv().body)

        req = f'DELETE /city/city-124 HTTP/1.1\r\nContent-Length: 0\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertEqual('403', sock.recv().status_code)

        req = f'GET /city HTTP/1.1\r\nContent-Length: 0\r\nAuthorization: valid_unit_test_token\r\n\r\n'
        sock.sendall(req.encode(UTF8))
        self.assertTrue('city-124' in sock.recv().body)

        sock._server._reset_resources()
