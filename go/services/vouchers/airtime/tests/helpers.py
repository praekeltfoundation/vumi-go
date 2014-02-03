from twisted.internet.defer import returnValue

from zope.interface import implements

from vumi.tests.helpers import (
    proxyable, generate_proxies, maybe_async, IHelper)

from go.base import utils as base_utils

from go.base.tests.helpers import DjangoVumiApiHelper


class ServiceHelper(object):
    implements(IHelper)

    def __init__(self, vumi_helper):
        self.is_sync = vumi_helper.is_sync
        self.vumi_helper = vumi_helper

    def setup(self):
        pass

    def cleanup(self):
        pass

    @proxyable
    @maybe_async
    def get_user_api(self):
        user_helper = yield self.vumi_helper.get_or_create_user()
        returnValue(user_helper.user_api)

    @proxyable
    @maybe_async
    def create_voucher_pool(self, name=u"test_pool", imports=[]):
        user_api = self.get_user_api()
        voucher_pool_store = user_api.airtime_voucher_pool_store
        pool = yield voucher_pool_store.new_voucher_pool(name, config={
            'ext_pool_name': name}, imports=imports)

        returnValue(pool)


class ServiceViewHelper(object):
    implements(IHelper)

    def __init__(self):
        self.vumi_helper = DjangoVumiApiHelper()
        self._service_helper = ServiceHelper(self.vumi_helper)

        generate_proxies(self, self._service_helper)
        generate_proxies(self, self.vumi_helper)

    def setup(self):
        # Create the things we need to create
        self.vumi_helper.setup()
        self.vumi_helper.make_django_user()

    def cleanup(self):
        return self.vumi_helper.cleanup()

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()
