import time
import json

from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.http import HttpResponse

from go.base.middleware import ResponseTimeMiddleware
from go.base.amqp import AmqpConnection

from mock import patch


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
        self.assertTrue(response['X-Response-Time'])

        call = publish.call_args
        args, kwargs = call
        command = json.loads(args[0])
        [datapoint] = command['datapoints']
        self.assertEqual(datapoint[0],
            'test.prefix.django.contrib.auth.views.login')
        self.assertEqual(datapoint[1], ['avg'])
        self.assertTrue(datapoint[2])
        self.assertEqual(kwargs['routing_key'], 'vumi.metrics')
        exchange = kwargs['exchange']
        self.assertEqual(exchange.name, 'vumi.metrics')
        self.assertEqual(exchange.type, 'direct')
