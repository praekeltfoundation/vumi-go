import json
import decimal
import pytest
import time

from twisted.internet import defer
from twisted.web import server
from twisted.trial import unittest

from go.billing import api
from go.billing.utils import DummySite


class UserTestCase(unittest.TestCase):
    @pytest.mark.django_db
    @defer.inlineCallbacks
    def setUp(self):
        connection_pool = yield api.start_connection_pool()
        self.web = DummySite(api.root)

    @pytest.mark.django_db
    def tearDown(self):
        api.stop_connection_pool()

    @pytest.mark.django_db
    @defer.inlineCallbacks
    def runTest(self):
        content = {
            'email': "test@example.com",
            'first_name': "Test",
            'last_name': "User",
            'password': "password"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post('users', args=None, content=content,
                                       headers=headers)

        self.assertEqual(response.responseCode, 200)

        user = json.loads(response.value(), parse_float=decimal.Decimal)
        self.assertTrue('id' in user)

        response = yield self.web.get('users')
        self.assertEqual(response.responseCode, 200)

        user_list = json.loads(response.value(), parse_float=decimal.Decimal)
        self.assertTrue(len(user_list) > 0)

        email_list = [u.get('email', None) for u in user_list]
        self.assertTrue("test@example.com" in email_list)
