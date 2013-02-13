import time
import logging

from django.core.urlresolvers import resolve, Resolver404
from django.conf import settings

from go.base.utils import vumi_api_for_user
from go.base.amqp import connection

from vumi.blinkenlights.metrics import AVG, MetricMessage

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
                                        request.method.upper())
            response_time = stop_time - request.start_time
            self.publish_metric(metric_name, response_time)
            response['X-Response-Time'] = response_time
        except (Resolver404, AttributeError), e:
            logger.exception(e)
        if response:
            return response

    def publish_metric(self, metric_name, value, timestamp=None,
                        aggregators=None):
        aggregators = aggregators or [AVG]
        timestamp = timestamp or time.time()
        metric_msg = MetricMessage()
        prefixed_metric_name = '%s%s' % (self.metrics_prefix, metric_name)
        metric_msg.append((prefixed_metric_name,
            tuple(sorted(agg.name for agg in aggregators)),
            [(timestamp, value)]))
        connection.publish_metric(metric_msg)
