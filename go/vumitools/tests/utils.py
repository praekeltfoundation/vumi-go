# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

import uuid

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import TestCase

from vumi.persist.fields import (
    ForeignKeyProxy, ManyToManyProxy, DynamicProxy, ListProxy)
from vumi.message import TransportEvent
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import VumiWorkerTestCase, PersistenceMixin

from go.vumitools.api import VumiApiCommand, VumiApi
from go.vumitools.account import UserAccount
from go.vumitools.contact import Contact, ContactGroup
from go.vumitools.utils import MessageMetadataHelper


def field_eq(f1, f2):
    if f1 == f2:
        return True
    if isinstance(f1, ManyToManyProxy) and isinstance(f2, ManyToManyProxy):
        return f1.keys() == f2.keys()
    if isinstance(f1, ForeignKeyProxy) and isinstance(f2, ForeignKeyProxy):
        return f1.key == f2.key
    if isinstance(f1, DynamicProxy) and isinstance(f2, DynamicProxy):
        return f1.items() == f2.items()
    if isinstance(f1, ListProxy) and isinstance(f2, ListProxy):
        return list(f1) == list(f2)
    return False


def model_eq(m1, m2):
    fields = m1.field_descriptors.keys()
    if fields != m2.field_descriptors.keys():
        return False
    if m1.key != m2.key:
        return False
    for field in fields:
        if not field_eq(getattr(m1, field), getattr(m2, field)):
            return False
    return True


class FakeAmqpConnection(object):
    def __init__(self, amqp_client):
        self._amqp = amqp_client
        self._connected = False
        self.commands = []

    def is_connected(self):
        return self._connected

    def connect(self, dsn=None):
        self._connected = True

    def publish_command_message(self, command):
        # This both sends messages via self._amqp and appends them to
        # self.commands to support to different use cases -- namely,
        # testing that messages are succesfully routed and testing that
        # the correct commands are queue for sending.
        self.commands.append(command)
        return self._amqp.publish_raw('vumi', 'vumi.api', command.to_json())

    def get_commands(self):
        commands, self.commands = self.commands, []
        return commands


class GoPersistenceMixin(PersistenceMixin):
    def _persist_setUp(self):
        self._users_created = 0
        return super(GoPersistenceMixin, self)._persist_setUp()

    @PersistenceMixin.sync_or_async
    def _clear_bucket_properties(self, account_keys, manager):
        # TODO: Fix this hackery when we can.
        import sys
        manager_module = sys.modules[manager.__module__]
        del_bp = getattr(manager_module, 'delete_bucket_properties', None)
        if del_bp is None:
            # This doesn't exist everywhere yet.
            return

        client = manager.client
        for account_key in account_keys:
            sub_manager = manager.sub_manager(account_key)
            yield del_bp(client.bucket(sub_manager.bucket_name(Contact)))
            yield del_bp(client.bucket(sub_manager.bucket_name(ContactGroup)))

    def _list_accounts(self, manager):
        bucket = manager.client.bucket(
            manager.bucket_name(UserAccount))
        if self.sync_persistence:
            return bucket.get_keys()
        return bucket.list_keys()

    @PersistenceMixin.sync_or_async
    def _persist_purge_riak(self, manager):
        # If buckets are empty, they aren't listed. However, they may still
        # have properties set. Therefore, we find all account keys and
        # clear properties from their associated buckets.
        accounts = yield self._list_accounts(manager)
        yield manager.purge_all()
        # This must happen after the objects are deleted, otherwise the
        # indexes don't go away.
        yield self._clear_bucket_properties(accounts, manager)

    def mk_config(self, config):
        config = super(GoPersistenceMixin, self).mk_config(config)
        return config

    @PersistenceMixin.sync_or_async
    def mk_user(self, vumi_api, username):
        key = u"test-%s-user" % (self._users_created,)
        self._users_created += 1
        user = vumi_api.account_store.users(key, username=username)
        yield user.save()
        returnValue(user)

    def get_vumi_api(self, config=None, amqp_client=None):
        if config is None:
            config = self.mk_config({})
        return VumiApi.from_config_async(config, amqp_client)


class GoWorkerTestMixin(GoPersistenceMixin):

    def _worker_name(self):
        return getattr(self.worker_class, 'worker_name', 'unnamed')

    def _command_rkey(self):
        return "%s.control" % (self._worker_name(),)

    @inlineCallbacks
    def setup_user_api(self, vumi_api, username=u'testuser'):
        user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_account_key = user_account.key
        self.user_api = self.vumi_api.get_user_api(self.user_account_key)

    def setup_tagpools(self):
        return self.setup_tagpool(u"pool", [u"tag1", u"tag2"])

    @inlineCallbacks
    def setup_tagpool(self, pool, tags, transport_name=None, metadata=None,
                      permission=True):
        tags = [(pool, tag) for tag in tags]
        if transport_name is None:
            transport_name = self.transport_name
        metadata = metadata.copy() if metadata is not None else {}
        metadata.setdefault("transport_type", self.transport_type)
        metadata.setdefault("transport_name", transport_name)
        yield self.vumi_api.tpm.declare_tags(tags)
        yield self.vumi_api.tpm.set_metadata(pool, metadata)
        if permission:
            yield self.add_tagpool_permission(pool)
        returnValue(tags)

    @inlineCallbacks
    def add_tagpool_permission(self, tagpool, max_keys=None):
        permission = yield self.user_api.api.account_store.tag_permissions(
            uuid.uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        yield permission.save()
        account = yield self.user_api.get_user_account()
        account.tagpools.add(permission)
        yield account.save()

    def dispatch_command(self, command, *args, **kw):
        cmd = VumiApiCommand.command(
            self._worker_name(), command, *args, **kw)
        return self._dispatch(cmd, self._command_rkey())

    def get_dispatcher_commands(self):
        return self._amqp.get_messages('vumi', 'vumi.api')

    def get_app_message_commands(self):
        return self._amqp.get_messages('vumi', self._command_rkey())

    def get_dispatched_app_events(self):
        return self._amqp.get_messages('vumi', 'vumi.event')

    def get_published_metrics(self, worker):
        return [
            (metric.name, value)
            for metric, ((time, value),) in worker.metrics._oneshot_msgs]

    @inlineCallbacks
    def create_conversation(self, started=False, **kw):
        conv_type = kw.pop('conversation_type', None)
        if conv_type is None:
            conv_type = self._conversation_type()
        name = kw.pop('name', u'Subject')
        description = kw.pop('description', u'')
        config = kw.pop('config', {})
        self.assertTrue(isinstance(config, dict))
        if started:
            kw.setdefault('status', u'running')
        conversation = yield self.user_api.new_conversation(
            conv_type, name, description, config, **kw)
        returnValue(self.user_api.wrap_conversation(conversation))


class GoAppWorkerTestMixin(GoWorkerTestMixin):

    def _worker_name(self):
        # DummyApplicationWorker has no worker_name attr.
        return getattr(self.application_class, 'worker_name', 'unnamed')

    def _conversation_type(self):
        # This is a guess based on worker_name.
        # We need a better way to do this.
        return self._worker_name().rpartition('_')[0].decode('utf-8')

    def add_conversation_md_to_msg(self, msg, conv, endpoint=None):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(self.vumi_api, msg)
        md.set_conversation_info(conv.conversation_type, conv.key)
        md.set_user_account(self.user_account_key)
        if endpoint is not None:
            msg.set_routing_endpoint(endpoint)

    @inlineCallbacks
    def start_conversation(self, conversation):
        old_cmds = len(self.get_dispatcher_commands())
        yield conversation.start()
        for cmd in self.get_dispatcher_commands()[old_cmds:]:
            yield self.dispatch_command(
                cmd.payload['command'], *cmd.payload['args'],
                **cmd.payload['kwargs'])

    @inlineCallbacks
    def stop_conversation(self, conversation):
        old_cmds = len(self.get_dispatcher_commands())
        yield conversation.stop_conversation()
        for cmd in self.get_dispatcher_commands()[old_cmds:]:
            yield self.dispatch_command(
                cmd.payload['command'], *cmd.payload['args'],
                **cmd.payload['kwargs'])

    def dispatch_to_conv(self, msg, conv):
        conv.set_go_helper_metadata(msg['helper_metadata'])
        return self.dispatch(msg)

    def dispatch_event_to_conv(self, event, conv):
        conv.set_go_helper_metadata(event['helper_metadata'])
        return self.dispatch_event(event)


class GoRouterWorkerTestMixin(GoWorkerTestMixin):

    def _worker_name(self):
        # DummyApplicationWorker has no worker_name attr.
        return getattr(self.router_class, 'worker_name', 'unnamed')

    def _router_type(self):
        # This is a guess based on worker_name.
        # We need a better way to do this.
        return self._worker_name().rpartition('_')[0].decode('utf-8')

    def setup_router(self, config, started=True, **kw):
        if started:
            kw['status'] = u'running'
        return self.create_router(config=config, **kw)

    def create_router(self, **kw):
        router_type = kw.pop('router_type', None)
        if router_type is None:
            router_type = self._router_type()
        name = kw.pop('name', u'Subject')
        description = kw.pop('description', u'')
        config = kw.pop('config', {})
        self.assertTrue(isinstance(config, dict))
        return self.user_api.new_router(
            router_type, name, description, config, **kw)

    @inlineCallbacks
    def start_router(self, router):
        router_api = self.user_api.get_router_api(
            router.router_type, router.key)
        yield router_api.start_router(router)
        for cmd in self.get_dispatcher_commands():
            yield self.dispatch_command(
                cmd.payload['command'], *cmd.payload['args'],
                **cmd.payload['kwargs'])

    @inlineCallbacks
    def stop_router(self, router):
        router_api = self.user_api.get_router_api(
            router.router_type, router.key)
        yield router_api.stop_router(router)
        for cmd in self.get_dispatcher_commands():
            yield self.dispatch_command(
                cmd.payload['command'], *cmd.payload['args'],
                **cmd.payload['kwargs'])

    def add_router_md_to_msg(self, msg, router, endpoint=None):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(self.vumi_api, msg)
        md.set_router_info(router.router_type, router.key)
        md.set_user_account(self.user_account_key)
        if endpoint is not None:
            msg.set_routing_endpoint(endpoint)

    def dispatch_inbound_to_router(self, msg, router, endpoint=None):
        self.add_router_md_to_msg(msg, router, endpoint)
        return self.dispatch_inbound(msg, 'ri_conn')

    def dispatch_outbound_to_router(self, msg, router, endpoint=None):
        self.add_router_md_to_msg(msg, router, endpoint)
        return self.dispatch_outbound(msg, 'ro_conn')

    def dispatch_event_to_router(self, msg, router, endpoint=None):
        self.add_router_md_to_msg(msg, router, endpoint)
        return self.dispatch_event(msg, 'ri_conn')


class AppWorkerTestCase(GoAppWorkerTestMixin, ApplicationTestCase):

    use_riak = True

    def publish_event(self, **kw):
        event = TransportEvent(**kw)
        d = self.dispatch(event, rkey=self.rkey('event'))
        d.addCallback(lambda _result: event)
        return d

    @inlineCallbacks
    def get_application(self, config, *args, **kw):
        if 'worker_name' not in config:
            config['worker_name'] = self._worker_name()
        worker = yield super(AppWorkerTestCase, self).get_application(
            config, *args, **kw)
        returnValue(worker)


class RouterWorkerTestCase(GoRouterWorkerTestMixin, VumiWorkerTestCase):

    use_riak = True

    def setUp(self):
        self._persist_setUp()
        super(RouterWorkerTestCase, self).setUp()

    @inlineCallbacks
    def tearDown(self):
        yield super(RouterWorkerTestCase, self).tearDown()
        yield self._persist_tearDown()

    def get_router_worker(self, config, start=True):
        if 'worker_name' not in config:
            config['worker_name'] = self._worker_name()
        if 'ri_connector_name' not in config:
            config['ri_connector_name'] = 'ri_conn'
        if 'ro_connector_name' not in config:
            config['ro_connector_name'] = 'ro_conn'
        return self.get_worker(
            config, self.router_class, start=start)


class GoWorkerTestCase(GoWorkerTestMixin, VumiWorkerTestCase):

    use_riak = True

    def setUp(self):
        self._persist_setUp()
        super(GoWorkerTestCase, self).setUp()

    @inlineCallbacks
    def tearDown(self):
        yield super(GoWorkerTestCase, self).tearDown()
        yield self._persist_tearDown()

    @inlineCallbacks
    def get_worker(self, config, *args, **kw):
        if 'worker_name' not in config:
            config['worker_name'] = self._worker_name()
        worker = yield super(GoWorkerTestCase, self).get_worker(
            config, self.worker_class, *args, **kw)
        returnValue(worker)


class GoTestCase(GoPersistenceMixin, TestCase):
    timeout = 5

    use_riak = False

    def setUp(self):
        self._persist_setUp()

    def tearDown(self):
        return self._persist_tearDown()
