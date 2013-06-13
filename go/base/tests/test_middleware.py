import time
import json

from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.http import HttpResponse

from go.api.go_api.session_manager import SessionManager
from go.base.amqp import AmqpConnection
from go.base.middleware import VumiUserApiMiddleware, ResponseTimeMiddleware
from go.base.tests.utils import VumiGoDjangoTestCase
from go.vumitools.api import VumiUserApi

from mock import patch


class VumiUserApiMiddlewareTestCase(VumiGoDjangoTestCase):
    def setUp(self):
        super(VumiUserApiMiddlewareTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()
        self.factory = RequestFactory()
        self.mw = VumiUserApiMiddleware()

    def test_unauthenticated_access(self):
        request = self.factory.get('/accounts/login/')
        self.mw.process_request(request)
        self.assertFalse(hasattr(request, 'user_api'))
        self.assertFalse(hasattr(request, 'session'))

    def test_authenticated_access(self):
        request = self.factory.get('/accounts/login/')
        request.user = self.user
        request.session = {}
        self.mw.process_request(request)
        self.assertTrue(isinstance(request.user_api, VumiUserApi))
        self.assertEqual(
            SessionManager.get_user_account_key(request.session),
            self.user.get_profile().user_account)


class ResponseTimeMiddlewareTestcase(TestCase):

    @override_settings(METRICS_PREFIX='test.prefix.')
    def setUp(self):
        self.factory = RequestFactory()
        self.mw = ResponseTimeMiddleware()

    def test_setting_start_time(self):
        request = self.factory.get('/accounts/login/')
        self.assertFalse(hasattr(request, 'start_time'))
        self.mw.process_request(request)
        self.assertTrue(request.start_time)

    @patch.object(AmqpConnection, 'is_connected')
    @patch.object(AmqpConnection, 'publish')
    def test_calculating_response_time(self, publish, is_connected):
        is_connected.return_value = True
        publish.return_value = True
        response = HttpResponse('ok')

        request = self.factory.get('/accounts/login/')
        request.start_time = time.time()

        self.mw.process_response(request, response)
        response_time_header = response['X-Response-Time']
        self.assertTrue(response_time_header)
        self.assertTrue(float(response_time_header))

        call = publish.call_args
        args, kwargs = call
        command = json.loads(args[0])
        [datapoint] = command['datapoints']
        self.assertEqual(datapoint[0],
            'test.prefix.django.contrib.auth.views.login.get')
        self.assertEqual(datapoint[1], ['avg'])
        self.assertTrue(datapoint[2])
        self.assertEqual(kwargs['routing_key'], 'vumi.metrics')
        exchange = kwargs['exchange']
        self.assertEqual(exchange.name, 'vumi.metrics')
        self.assertEqual(exchange.type, 'direct')

    @patch.object(AmqpConnection, 'is_connected')
    @patch.object(AmqpConnection, 'publish')
    def test_method_differentiation(self, publish, is_connected):
        is_connected.return_value = True
        publish.return_value = True
        response = HttpResponse('ok')

        request = self.factory.post('/accounts/login/')
        request.start_time = time.time()
        self.mw.process_response(request, response)

        call = publish.call_args
        args, kwargs = call
        command = json.loads(args[0])
        [datapoint] = command['datapoints']
        self.assertEqual(datapoint[0],
            'test.prefix.django.contrib.auth.views.login.post')
