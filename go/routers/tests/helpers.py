from twisted.internet.defer import inlineCallbacks, returnValue

from zope.interface import implements

from vumi.tests.helpers import (
    MessageDispatchHelper, proxyable, generate_proxies, maybe_async, IHelper)

from go.vumitools.api import VumiApiCommand, VumiApiEvent
from go.vumitools.tests.helpers import GoMessageHelper, VumiApiHelper


class RouterHelper(object):
    implements(IHelper)

    def __init__(self, router_type, vumi_helper):
        self.is_sync = vumi_helper.is_sync
        self._router_type = router_type
        self.vumi_helper = vumi_helper

    def setup(self):
        pass

    def cleanup(self):
        pass

    @proxyable
    @maybe_async
    def create_group_with_contacts(self, group_name, contact_count):
        group = yield self.create_group(group_name)
        for i in range(contact_count):
            yield self.create_contact(
                msisdn=u'+27831234567{0}'.format(i), groups=[group],
                name=u"Contact", surname=u"%s" % (i,))
        returnValue(group)

    @proxyable
    @maybe_async
    def create_group(self, group_name):
        user_helper = yield self.vumi_helper.get_or_create_user()
        contact_store = user_helper.user_api.contact_store
        group = yield contact_store.new_group(group_name)
        returnValue(group)

    @proxyable
    @maybe_async
    def create_smart_group(self, group_name, query):
        user_helper = yield self.vumi_helper.get_or_create_user()
        contact_store = user_helper.user_api.contact_store
        group = yield contact_store.new_smart_group(group_name, query)
        returnValue(group)

    @proxyable
    @maybe_async
    def create_contact(self, msisdn, **kw):
        kw.setdefault('name', u"First")
        kw.setdefault('surname', u"Last")
        user_helper = yield self.vumi_helper.get_or_create_user()
        contact_store = user_helper.user_api.contact_store
        contact = yield contact_store.new_contact(msisdn=msisdn, **kw)
        returnValue(contact)

    @proxyable
    @maybe_async
    def create_router(self, started=False, **router_kw):
        user_helper = yield self.vumi_helper.get_or_create_user()
        router = yield user_helper.create_router(
            self._router_type, started=started, **router_kw)
        returnValue(router)

    @proxyable
    @maybe_async
    def create_channel(self, metadata=None):
        yield self.vumi_helper.setup_tagpool(u"pool", [u"tag"], metadata)
        user_helper = yield self.vumi_helper.get_or_create_user()
        yield user_helper.add_tagpool_permission(u"pool")
        yield user_helper.user_api.acquire_specific_tag((u"pool", u"tag"))
        channel = yield user_helper.user_api.get_channel((u"pool", u"tag"))
        returnValue(channel)

    @proxyable
    @maybe_async
    def get_router(self, router_key):
        user_helper = yield self.vumi_helper.get_or_create_user()
        router = yield user_helper.get_router(router_key)
        returnValue(router)


class RouterConnectorHelper(object):
    implements(IHelper)

    def __init__(self, connector_name, vumi_helper, msg_helper):
        self.connector_name = connector_name
        self._worker_helper = vumi_helper.get_worker_helper(
            connector_name)
        self._dispatch_helper = MessageDispatchHelper(
            msg_helper, self._worker_helper)
        generate_proxies(self, self._worker_helper)
        generate_proxies(self, self._dispatch_helper)

    @inlineCallbacks
    def cleanup(self):
        yield self._dispatch_helper.cleanup()
        yield self._worker_helper.cleanup()


class RouterWorkerHelper(object):
    implements(IHelper)

    def __init__(self, worker_class, **msg_helper_args):
        self._worker_class = worker_class
        msg_helper_kw = {}
        if msg_helper_args is not None:
            msg_helper_kw.update(msg_helper_args)

        self.vumi_helper = VumiApiHelper()
        self._router_helper = RouterHelper(
            self._router_type(), self.vumi_helper)
        self.msg_helper = GoMessageHelper(**msg_helper_kw)

        # Proxy methods from our helpers.
        generate_proxies(self, self._router_helper)
        generate_proxies(self, self.msg_helper)

        self.ri = RouterConnectorHelper(
            'ri_conn', self.vumi_helper, self.msg_helper)

        self.ro = RouterConnectorHelper(
            'ro_conn', self.vumi_helper, self.msg_helper)

    def _worker_name(self):
        return self._worker_class.worker_name

    def _router_type(self):
        # This is a guess based on worker_name.
        # We need a better way to do this.
        return self._worker_name().rpartition('_')[0].decode('utf-8')

    def setup(self):
        self.vumi_helper.setup(setup_vumi_api=False)

    @inlineCallbacks
    def cleanup(self):
        yield self.ro.cleanup()
        yield self.ri.cleanup()
        yield self.msg_helper.cleanup()
        yield self.vumi_helper.cleanup()

    @inlineCallbacks
    def get_router_worker(self, config=None, start=True):
        # Note: We assume that this is called exactly once per test.
        config = self.vumi_helper.mk_config(config or {})
        config.setdefault('worker_name', self._worker_name())
        config.setdefault('ri_connector_name', self.ri.connector_name)
        config.setdefault('ro_connector_name', self.ro.connector_name)
        worker = yield self.ri.get_worker(self._worker_class, config, start)
        # Set up our other bits of helper.
        self.vumi_helper.set_vumi_api(worker.vumi_api)
        returnValue(worker)

    @inlineCallbacks
    def start_router(self, router):
        assert self._get_pending_commands() == [], (
            "Found pending commands while starting router, aborting.")
        user_helper = yield self.vumi_helper.get_or_create_user()
        router_api = user_helper.user_api.get_router_api(
            router.router_type, router.key)
        yield router_api.start_router(router)
        yield self.dispatch_commands_to_router()

    @inlineCallbacks
    def stop_router(self, router):
        assert self._get_pending_commands() == [], (
            "Found pending commands while stopping router, aborting.")
        user_helper = yield self.vumi_helper.get_or_create_user()
        router_api = user_helper.user_api.get_router_api(
            router.router_type, router.key)
        yield router_api.stop_router(router)
        yield self.dispatch_commands_to_router()

    def _get_pending_commands(self):
        return self.ri.get_dispatched('vumi', 'api', VumiApiCommand)

    @inlineCallbacks
    def dispatch_commands_to_router(self):
        pending_commands = self._get_pending_commands()
        self.ri._worker_helper._clear_dispatched('vumi', 'api')
        for command in pending_commands:
            yield self.ri.dispatch_raw(
                "%s.control" % (self._worker_name(),), command)

    @inlineCallbacks
    def dispatch_command(self, command, *args, **kw):
        cmd = VumiApiCommand.command(
            self._worker_name(), command, *args, **kw)
        yield self.ri.dispatch_raw('vumi.api', cmd)
        yield self.dispatch_commands_to_router()

    def get_published_metrics(self, worker):
        return [
            (metric.name, value)
            for metric, ((time, value),) in worker.metrics._oneshot_msgs]

    def get_dispatched_router_events(self):
        return self.get_dispatched('vumi', 'event', VumiApiEvent)
