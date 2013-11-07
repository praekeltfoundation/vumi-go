import time
import logging

from django.core.urlresolvers import resolve, Resolver404

from go.base.utils import vumi_api_for_user
from go.vumitools.metrics import DjangoMetric
from go.api.go_api.session_manager import SessionManager

logger = logging.getLogger(__name__)


class VumiUserApiMiddleware(object):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated():
            user_api = vumi_api_for_user(request.user)
            request.user_api = user_api
            SessionManager.set_user_account_key(
                request.session, user_api.user_account_key)


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
        return DjangoMetric(metric_name.lower())

    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, request, response):
        try:
            response_time = request.start_time - time.time()
            response['X-Response-Time'] = response_time

            metric = self.metric_from_request(request)
            metric.oneshot(response_time)
        except AttributeError, e:
            # For cases where our request object was not processed and given a
            # `start_time` attribute
            logger.exception(e)
        except Resolver404:
            # Ignoring the Resolver404 as that just means we've not found a
            # page and any response metric on that will not be of interest
            # to us.
            pass
        if response:
            return response
