import time
import logging

from django.core.urlresolvers import resolve, Resolver404
from django.conf import settings

from go.base.utils import vumi_api_for_user
from go.base.amqp import connection

from vumi.blinkenlights.metrics import AVG

logger = logging.getLogger(__name__)


class VumiUserApiMiddleware(object):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated():
            request.user_api = vumi_api_for_user(request.user)


class ResponseTimeMiddleware(object):
    """
    Middleware for generating metrics on page response times.

    Marks the time when a request is received and when the response for that
    request is sent back again. Fires off metrics for the time taken to
    generate the response.

    It sets an X-Response-Time HTTP header which can be useful for debugging
    or logging slow resources upstream.
    """
    def __init__(self):
        self.metrics_prefix = getattr(settings, 'METRICS_PREFIX', 'go.django.')

    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, request, response):
        try:
            stop_time = time.time()
            func = resolve(request.path)[0]
            metric_name = '%s.%s.%s' % (func.__module__, func.__name__,
                                        request.method.lower())
            response_time = stop_time - request.start_time
            self.publish_metric(metric_name, response_time)
            response['X-Response-Time'] = response_time
        except AttributeError, e:
            logger.exception(e)
        except Resolver404:
            # Ignoring the Resolver404 as that just means we've not found a
            # page and any response metric on that will not be of interest
            # to us.
            pass
        if response:
            return response

    def publish_metric(self, metric_name, value, timestamp=None,
                        aggregators=None):
        aggregators = aggregators or [AVG]
        prefixed_metric_name = '%s%s' % (self.metrics_prefix, metric_name)
        connection.publish_metric(prefixed_metric_name, aggregators,
            value, timestamp)
