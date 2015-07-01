import time
import logging

from django.core.urlresolvers import resolve, Resolver404
from vumi.blinkenlights.metrics import Metric

from go.api.go_api.session_manager import SessionManager
from go.base.utils import vumi_api, vumi_api_for_user
from go.vumitools.metrics import get_django_metric_prefix

logger = logging.getLogger(__name__)


class VumiUserApiMiddleware(object):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated():
            user_api = vumi_api_for_user(request.user)
            request.user_api = user_api
            SessionManager.set_user_account_key(
                request.session, user_api.user_account_key)

    def _cleanup_user_api(self, request):
        try:
            user_api = request.user_api
        except AttributeError:
            # Ignoring AttributeError as that just means this request wasn't
            # seen by process_request (this is normal when other middleware
            # returns a response).
            return
        user_api.close()

    def process_response(self, request, response):
        self._cleanup_user_api(request)
        return response

    def process_exception(self, request, exception):
        self._cleanup_user_api(request)


class ResponseTimeMiddleware(object):
    """
    Middleware for generating metrics on page response times.

    Marks the time when a request is received and when the response for that
    request is sent back again. Fires off metrics for the time taken to
    generate the response.

    It sets an X-Response-Time HTTP header which can be useful for debugging
    or logging slow resources upstream.
    """
    @classmethod
    def metric_from_request(cls, request):
        func = resolve(request.path)[0]
        metric_name = '%s.%s.%s' % (
            func.__module__, func.__name__, request.method)
        return Metric(metric_name.lower())

    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, request, response):
        try:
            start_time = request.start_time
        except AttributeError:
            # Ignoring AttributeError as that just means this request wasn't
            # seen by process_request (this is normal when other middleware
            # returns a response).
            return response

        try:
            metric = self.metric_from_request(request)
        except Resolver404:
            # Ignoring the Resolver404 as that just means we've not found a
            # page and any response metric on that will not be of interest
            # to us.
            return response

        response_time = start_time - time.time()
        response['X-Response-Time'] = response_time
        # TODO: Better way to fire these metrics.
        api = vumi_api()
        try:
            metrics = api.get_metric_manager(get_django_metric_prefix())
            metrics.oneshot(metric, response_time)
            metrics.publish_metrics()
        finally:
            api.close()
        return response
