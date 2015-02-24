from twisted.internet.defer import inlineCallbacks, returnValue

from zope.interface import implements

from vumi.tests.helpers import (
    MessageDispatchHelper, proxyable, generate_proxies, maybe_async, IHelper)

from go.vumitools.api import VumiApiCommand, VumiApiEvent
from go.vumitools.tests.helpers import GoMessageHelper, VumiApiHelper


class ApplicationHelper(object):
    implements(IHelper)

    def __init__(self, conversation_type, vumi_helper):
        self.is_sync = vumi_helper.is_sync
        self._conversation_type = conversation_type
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
    def create_contact(self, msisdn, **kw):
        kw.setdefault('name', "First")
        kw.setdefault('surname', "Last")
        user_helper = yield self.vumi_helper.get_or_create_user()
        contact_store = user_helper.user_api.contact_store
        contact = yield contact_store.new_contact(msisdn=msisdn, **kw)
        returnValue(contact)

    @proxyable
    @maybe_async
    def create_conversation(self, started=False, channel=None, **conv_kw):
        user_helper = yield self.vumi_helper.get_or_create_user()
        conversation = yield user_helper.create_conversation(
            self._conversation_type, started=started, **conv_kw)
        if channel is not None:
            user_account = user_helper.get_user_account()
            rt = user_account.routing_table
            rt.add_entry(
                conversation.get_connector(), 'default',
                channel.get_connector(), 'default')
            rt.add_entry(
                channel.get_connector(), 'default',
                conversation.get_connector(), 'default')
            yield user_account.save()
        returnValue(conversation)

    @proxyable
    @maybe_async
    def create_channel(self, metadata=None, supports_generic_sends=None):
        if supports_generic_sends is not None:
            if metadata is None:
                metadata = {}
            supports = metadata.setdefault('supports', {})
            supports['generic_sends'] = supports_generic_sends
        yield self.vumi_helper.setup_tagpool(u"pool", [u"tag"], metadata)
        user_helper = yield self.vumi_helper.get_or_create_user()
        yield user_helper.add_tagpool_permission(u"pool")
        yield user_helper.user_api.acquire_specific_tag((u"pool", u"tag"))
        channel = yield user_helper.user_api.get_channel((u"pool", u"tag"))
        returnValue(channel)

    @proxyable
    @maybe_async
    def get_conversation(self, conversation_key):
        user_helper = yield self.vumi_helper.get_or_create_user()
        conversation = yield user_helper.get_conversation(conversation_key)
        returnValue(conversation)


class AppWorkerHelper(object):
    implements(IHelper)

    def __init__(self, worker_class, **msg_helper_args):
        self._worker_class = worker_class

        self.vumi_helper = VumiApiHelper()
        self._app_helper = ApplicationHelper(
            self._conversation_type(), self.vumi_helper)
        self.msg_helper = GoMessageHelper(**msg_helper_args)
        self.transport_name = self.msg_helper.transport_name
        self.worker_helper = self.vumi_helper.get_worker_helper(
            self.transport_name)
        self.dispatch_helper = MessageDispatchHelper(
            self.msg_helper, self.worker_helper)

        # Proxy methods from our helpers.
        generate_proxies(self, self._app_helper)
        generate_proxies(self, self.msg_helper)
        generate_proxies(self, self.worker_helper)
        generate_proxies(self, self.dispatch_helper)

    def _worker_name(self):
        return self._worker_class.worker_name

    def _conversation_type(self):
        # This is a guess based on worker_name.
        # TODO: We need a better way to do this, probably involving either the
        #       conversation definition or go.config.
        return self._worker_name().rpartition('_')[0].decode('utf-8')

    def setup(self):
        return self.vumi_helper.setup(setup_vumi_api=False)

    def cleanup(self):
        return self.vumi_helper.cleanup()

    @inlineCallbacks
    def get_app_worker(self, config=None, start=True):
        # Note: We assume that this is called exactly once per test.
        config = self.vumi_helper.mk_config(config or {})
        config.setdefault('worker_name', self._worker_name())
        config.setdefault('transport_name', self.msg_helper.transport_name)
        worker = yield self.get_worker(self._worker_class, config, start)
        # Set up our other bits of helper.
        self.vumi_helper.set_vumi_api(worker.vumi_api)
        self.msg_helper.mdb = worker.vumi_api.mdb
        returnValue(worker)

    @inlineCallbacks
    def start_conversation(self, conversation):
        assert self._get_pending_commands() == [], (
            "Found pending commands while starting conversation, aborting.")
        yield conversation.start()
        yield self.dispatch_commands_to_app()

    @inlineCallbacks
    def stop_conversation(self, conversation):
        assert self._get_pending_commands() == [], (
            "Found pending commands while stopping conversation, aborting.")
        yield conversation.stop_conversation()
        yield self.dispatch_commands_to_app()

    def _get_pending_commands(self):
        return self.worker_helper.get_dispatched('vumi', 'api', VumiApiCommand)

    @inlineCallbacks
    def dispatch_commands_to_app(self):
        pending_commands = self._get_pending_commands()
        self.worker_helper._clear_dispatched('vumi', 'api')
        for command in pending_commands:
            yield self.worker_helper.dispatch_raw(
                "%s.control" % (self._worker_name(),), command)

    @inlineCallbacks
    def dispatch_command(self, command, *args, **kw):
        cmd = VumiApiCommand.command(
            self._worker_name(), command, *args, **kw)
        yield self.worker_helper.dispatch_raw('vumi.api', cmd)
        yield self.dispatch_commands_to_app()

    def get_published_metrics(self, worker):
        metrics = []
        for metric_msg in self.worker_helper.get_dispatched_metrics():
            for name, _aggs, data in metric_msg:
                for _time, value in data:
                    metrics.append((name, value))
        return metrics

    def get_published_metrics_with_aggs(self, worker):
        metrics = []
        for metric_msg in self.worker_helper.get_dispatched_metrics():
            for name, aggs, data in metric_msg:
                for _time, value in data:
                    for agg in aggs:
                        metrics.append((name, value, agg))
        return metrics

    def get_dispatched_app_events(self):
        return self.worker_helper.get_dispatched('vumi', 'event', VumiApiEvent)
