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
        self.router_wrapper = None

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
    def create_contact(self, msisdn, **kw):
        kw.setdefault('name', "First")
        kw.setdefault('surname', "Last")
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
        if self.router_wrapper is not None:
            router = self.router_wrapper(router)
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
        self.ri_connector_name = 'ri_conn'
        self.ro_connector_name = 'ro_conn'

        # Proxy methods from our helpers.
        generate_proxies(self, self._router_helper)
        generate_proxies(self, self.msg_helper)

        # We need versions of these for both inbound and outbound so we can't
        # generate proxies automagically.
        # TODO: Build some mechanism for grouping sets of proxies together.
        self._ri_worker_helper = self.vumi_helper.get_worker_helper(
            self.ri_connector_name)
        self._ri_dispatch_helper = MessageDispatchHelper(
            self.msg_helper, self._ri_worker_helper)
        # Grab all proxies for these ones. We'll override the RO versions.
        generate_proxies(self, self._ri_worker_helper)
        generate_proxies(self, self._ri_dispatch_helper)

        self._ro_worker_helper = self.vumi_helper.get_worker_helper(
            self.ro_connector_name)
        self._ro_dispatch_helper = MessageDispatchHelper(
            self.msg_helper, self._ro_worker_helper)

        self._override_proxies(self._ro_worker_helper, [
            'get_dispatched_events',
            'get_dispatched_inbound',
            'wait_for_dispatched_events',
            'wait_for_dispatched_inbound',
            'clear_dispatched_events',
            'clear_dispatched_inbound',
            'dispatch_outbound',
        ])
        self._override_proxies(self._ro_dispatch_helper, [
            'make_dispatch_outbound',
        ])

    def _override_proxies(self, source, methods):
        for method in methods:
            setattr(self, method, getattr(source, method))

    def _worker_name(self):
        return self._worker_class.worker_name

    def _router_type(self):
        # This is a guess based on worker_name.
        # We need a better way to do this.
        return self._worker_name().rpartition('_')[0].decode('utf-8')

    def setup(self):
        pass

    @inlineCallbacks
    def cleanup(self):
        yield self._ro_worker_helper.cleanup()
        yield self._ri_worker_helper.cleanup()
        yield self.vumi_helper.cleanup()

    @inlineCallbacks
    def get_router_worker(self, config=None, start=True):
        # Note: We assume that this is called exactly once per test.
        config = self.vumi_helper.mk_config(config or {})
        config.setdefault('worker_name', self._worker_name())
        config.setdefault('ri_connector_name', self.ri_connector_name)
        config.setdefault('ro_connector_name', self.ro_connector_name)
        worker = yield self.get_worker(self._worker_class, config, start)
        # Set up our other bits of helper.
        self.vumi_helper.set_vumi_api(worker.vumi_api)
        self.msg_helper.mdb = worker.vumi_api.mdb
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
        return self.get_dispatched('vumi', 'api', VumiApiCommand)

    @inlineCallbacks
    def dispatch_commands_to_router(self):
        pending_commands = self._get_pending_commands()
        self._ri_worker_helper._clear_dispatched('vumi', 'api')
        for command in pending_commands:
            yield self.dispatch_raw(
                "%s.control" % (self._worker_name(),), command)

    @inlineCallbacks
    def dispatch_command(self, command, *args, **kw):
        cmd = VumiApiCommand.command(
            self._worker_name(), command, *args, **kw)
        yield self.dispatch_raw('vumi.api', cmd)
        yield self.dispatch_commands_to_router()

    def get_published_metrics(self, worker):
        return [
            (metric.name, value)
            for metric, ((time, value),) in worker.metrics._oneshot_msgs]

    def get_dispatched_router_events(self):
        return self.get_dispatched('vumi', 'event', VumiApiEvent)
