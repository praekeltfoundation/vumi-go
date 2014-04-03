from twisted.internet.defer import returnValue

from zope.interface import implements

from vumi.tests.helpers import proxyable, maybe_async, IHelper


class ServiceComponentHelper(object):
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
