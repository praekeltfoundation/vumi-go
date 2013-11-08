from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import (
    WorkerHelper, MessageDispatchHelper, proxyable, generate_proxies)
from vumi.tests.utils import PersistenceMixin  # For .sync_or_async()

from go.vumitools.api import VumiApiCommand
from go.vumitools.tests.helpers import GoMessageHelper, VumiApiHelper


class ApplicationHelper(object):
    # TODO: Avoid having to pass the TestCase in here. This requires a
    #       persistence helper which we don't have yet.
    def __init__(self, test_case, conversation_type, vumi_helper):
        self.sync_persistence = test_case.sync_persistence
        self._test_case = test_case
        self._conversation_type = conversation_type
        self.vumi_helper = vumi_helper
        self.conversation_wrapper = None

    def cleanup(self):
        pass

    @proxyable
    @PersistenceMixin.sync_or_async
    def create_group_with_contacts(self, group_name, contact_count):
        user_helper = yield self.vumi_helper.get_or_create_user()
        contact_store = user_helper.user_api.contact_store
        group = yield contact_store.new_group(group_name)
        for i in range(contact_count):
            yield contact_store.new_contact(
                name=u"Contact", surname=u"%s" % (i,),
                msisdn=u'+27831234567{0}'.format(i), groups=[group])
        returnValue(group)

    @proxyable
    @PersistenceMixin.sync_or_async
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
        if self.conversation_wrapper is not None:
            conversation = self.conversation_wrapper(conversation)
        returnValue(conversation)

    @proxyable
    @PersistenceMixin.sync_or_async
    def create_channel(self, metadata=None):
        yield self.vumi_helper.setup_tagpool(u"pool", [u"tag"], metadata)
        user_helper = yield self.vumi_helper.get_or_create_user()
        yield user_helper.add_tagpool_permission(u"pool")
        yield user_helper.user_api.acquire_specific_tag((u"pool", u"tag"))
        channel = yield user_helper.user_api.get_channel((u"pool", u"tag"))
        returnValue(channel)

    @proxyable
    @PersistenceMixin.sync_or_async
    def get_conversation(self, conversation_key):
        user_helper = yield self.vumi_helper.get_or_create_user()
        conversation = yield user_helper.get_conversation(conversation_key)
        returnValue(conversation)


class AppWorkerHelper(object):
    # TODO: Avoid having to pass the TestCase in here. This requires a
    #       persistence helper which we don't have yet.
    def __init__(self, test_case, worker_class, msg_helper_args=None):
        self._test_case = test_case
        self._worker_class = worker_class
        msg_helper_kw = {}
        if msg_helper_args is not None:
            msg_helper_kw.update(msg_helper_args)

        self.vumi_helper = VumiApiHelper(test_case)
        self._app_helper = ApplicationHelper(
            test_case, self._conversation_type(), self.vumi_helper)
        self.msg_helper = GoMessageHelper(**msg_helper_kw)
        self.transport_name = self.msg_helper.transport_name
        self.worker_helper = WorkerHelper(self.transport_name)
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
        # We need a better way to do this.
        return self._worker_name().rpartition('_')[0].decode('utf-8')

    @inlineCallbacks
    def cleanup(self):
        yield self.worker_helper.cleanup()
        yield self.vumi_helper.cleanup()

    @inlineCallbacks
    def get_app_worker(self, config=None, start=True):
        # Note: We assume that this is called exactly once per test.
        config = self._test_case.mk_config(config or {})
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
        print pending_commands
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
        return [
            (metric.name, value)
            for metric, ((time, value),) in worker.metrics._oneshot_msgs]
