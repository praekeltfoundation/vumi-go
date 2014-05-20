from twisted.internet.defer import returnValue
from zope.interface import implements

from vumi.tests.helpers import (
    proxyable, generate_proxies, maybe_async, IHelper)

from go.vumitools.tests.helpers import VumiApiHelper


class ServiceHelper(object):
    implements(IHelper)

    def __init__(self, service_type, vumi_helper):
        self.is_sync = vumi_helper.is_sync
        self._service_type = service_type
        self.vumi_helper = vumi_helper

    def setup(self):
        pass

    def cleanup(self):
        pass

    @proxyable
    @maybe_async
    def create_service_component(self, started=False, **service_kw):
        user_helper = yield self.vumi_helper.get_or_create_user()
        service = yield user_helper.create_service_component(
            self._service_type, started=started, **service_kw)
        returnValue(service)

    @proxyable
    @maybe_async
    def get_service_component(self, service_key):
        user_helper = yield self.vumi_helper.get_or_create_user()
        service = yield user_helper.get_service_component(service_key)
        returnValue(service)

    @proxyable
    @maybe_async
    def get_service_component_api(self, service_key):
        user_helper = yield self.vumi_helper.get_or_create_user()
        service_api = yield user_helper.user_api.get_service_component_api(
            self._service_type, service_key)
        returnValue(service_api)


class ServiceComponentHelper(object):
    implements(IHelper)

    def __init__(self, service_type, is_sync):
        self.service_type = service_type

        self.vumi_helper = VumiApiHelper(is_sync=is_sync)
        self._service_helper = ServiceHelper(service_type, self.vumi_helper)

        # Proxy methods from our helpers.
        generate_proxies(self, self._service_helper)
        generate_proxies(self, self.vumi_helper)

    def setup(self):
        return self.vumi_helper.setup()

    def cleanup(self):
        return self.vumi_helper.cleanup()

    def get_published_metrics(self):
        metrics = []
        worker_helper = self.vumi_helper.get_worker_helper()
        for metric_msg in worker_helper.get_dispatched_metrics():
            for name, _aggs, data in metric_msg:
                for _time, value in data:
                    metrics.append((name, value))
        return metrics
