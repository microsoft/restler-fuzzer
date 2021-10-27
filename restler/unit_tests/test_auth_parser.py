import unittest

from engine.core.request_utilities import parse_authentication_tokens, NO_TOKEN_SPECIFIED, NO_SHADOW_TOKEN_SPECIFIED

class AuthParserTest(unittest.TestCase):
    def test_auth_parser(self):
        global latest_token_value, latest_shadow_token_value
        latest_token_value = NO_TOKEN_SPECIFIED
        latest_shadow_token_value = NO_SHADOW_TOKEN_SPECIFIED

        testcases = [
            ("{u'app1': {}}\nApiTokenTag: 9A\n", ('ApiTokenTag: 9A\r\n', NO_SHADOW_TOKEN_SPECIFIED)),
            ("{u'app1': {}}\nApiTokenTag: 9A\nApiTokenTag2: 9B\n", ('ApiTokenTag: 9A\r\nApiTokenTag2: 9B\r\n', NO_SHADOW_TOKEN_SPECIFIED)),
            ("{u'app1': {}}\nApiTokenTag: 9A\nApiTokenTag2: 9B\n---\n", ('ApiTokenTag: 9A\r\nApiTokenTag2: 9B\r\n', NO_SHADOW_TOKEN_SPECIFIED)),

            ("{u'app1': {}, u'app2': {}}\nApiTokenTag: 9A\nApiTokenTag: 9B\n", ('ApiTokenTag: 9A\r\n', 'ApiTokenTag: 9B\r\n')),
            ("{u'app1': {}, u'app2': {}}\nApiTokenTag: 9A\n---\nApiTokenTag: 9B\n", ('ApiTokenTag: 9A\r\n', 'ApiTokenTag: 9B\r\n')),
            ("{u'app1': {}, u'app2': {}}\nApiTokenTag: 9A\nApiTokenTag2: 9C\n---\nApiTokenTag: 9B\nApiTokenTag2: 9D\n", ('ApiTokenTag: 9A\r\nApiTokenTag2: 9C\r\n', 'ApiTokenTag: 9B\r\nApiTokenTag2: 9D\r\n')),
        ]
        for data, expected in testcases:
            latest_token_value = NO_TOKEN_SPECIFIED
            latest_shadow_token_value = NO_SHADOW_TOKEN_SPECIFIED
            _, latest_token_value, latest_shadow_token_value = parse_authentication_tokens(data)
            self.assertEqual(expected, (latest_token_value, latest_shadow_token_value))
