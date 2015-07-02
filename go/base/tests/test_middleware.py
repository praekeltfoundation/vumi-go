import time
from django.http import HttpResponse
from django.test.client import RequestFactory

from go.api.go_api.session_manager import SessionManager
from go.base.middleware import VumiUserApiMiddleware, ResponseTimeMiddleware
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.vumitools.api import VumiUserApi


class TestVumiUserApiMiddleware(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

        self.factory = RequestFactory()
        self.mw = VumiUserApiMiddleware()

    def test_unauthenticated_access(self):
        request = self.factory.get('/accounts/login/')
        self.mw.process_request(request)
        self.assertFalse(hasattr(request, 'user_api'))
        self.assertFalse(hasattr(request, 'session'))
        # process_response() has nothing to clean up, but it should return
        # the response object we give it.
        response = object()
        self.assertEqual(response, self.mw.process_response(request, response))

    def test_authenticated_access(self):
        request = self.factory.get('/accounts/login/')
        request.user = self.user_helper.get_django_user()
        request.session = {}
        self.mw.process_request(request)
        self.assertTrue(isinstance(request.user_api, VumiUserApi))
        self.assertEqual(
            SessionManager.get_user_account_key(request.session),
            self.user_helper.account_key)
        # process_response() should clean up the VumiUserApi on the request and
        # return the response object we give it.
        response = object()
        self.assertEqual(response, self.mw.process_response(request, response))


class ResponseTimeMiddlewareTestcase(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper(), setup_vumi_api=False)
        self.factory = RequestFactory()
        self.mw = ResponseTimeMiddleware()

    def test_setting_start_time(self):
        request = self.factory.get('/accounts/login/')
        self.assertFalse(hasattr(request, 'start_time'))
        self.mw.process_request(request)
        self.assertTrue(request.start_time)

    def test_calculating_response_time(self):
        response = HttpResponse('ok')

        request = self.factory.get('/accounts/login/')
        request.start_time = time.time()

        self.mw.process_response(request, response)
        response_time_header = response['X-Response-Time']
        self.assertTrue(response_time_header)
        self.assertTrue(float(response_time_header))

        [metric] = self.vumi_helper.amqp_connection.get_metrics()
        [datapoint] = metric['datapoints']
        self.assertEqual(datapoint[0],
            'go.django.django.contrib.auth.views.login.get')
        self.assertEqual(datapoint[1], ('avg',))
        self.assertTrue(datapoint[2])

    def test_method_differentiation(self):
        response = HttpResponse('ok')

        request = self.factory.post('/accounts/login/')
        request.start_time = time.time()
        self.mw.process_response(request, response)

        [metric] = self.vumi_helper.amqp_connection.get_metrics()
        [datapoint] = metric['datapoints']
        self.assertEqual(datapoint[0],
            'go.django.django.contrib.auth.views.login.post')
