# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

import os
import uuid
from contextlib import contextmanager

from twisted.python.monkey import MonkeyPatcher
from twisted.internet.defer import inlineCallbacks, returnValue
from celery.app import app_or_default

from vumi.persist.fields import (
    ForeignKeyProxy, ManyToManyProxy, DynamicProxy, ListProxy)
from vumi.message import TransportEvent
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import PersistenceMixin

from go.vumitools.api import VumiApiCommand
from go.vumitools.account import UserAccount
from go.vumitools.contact import Contact, ContactGroup


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


class RabbitConsumerFactory(object):
    def teardown(self):
        pass

    def get_consumer(self, app, **options):
        connection = app.broker_connection()
        consumer = app.amqp.TaskConsumer(connection=connection,
                                         **options)
        # clear out old messages
        while True:
            msg = consumer.fetch()
            if msg is None:
                break
        return consumer


class DummyConsumerFactory(object):

    class DummyConsumer(object):
        def __init__(self, factory):
            self.factory = factory

        def fetch(self):
            return self.factory.fetch()

    class DummyPublisher(object):
        def __init__(self, factory):
            self.factory = factory

        def publish(self, payload):
            self.factory.publish(payload)

    class DummyMessage(object):
        def __init__(self, payload):
            self.payload = payload

    def __init__(self):
        import go.vumitools.api_celery
        self.queue = []
        self.monkey = MonkeyPatcher((go.vumitools.api_celery, "get_publisher",
                                     self.get_publisher))
        self.monkey.patch()

    def teardown(self):
        self.monkey.restore()

    def publish(self, payload):
        self.queue.append(self.DummyMessage(payload))

    def fetch(self):
        if not self.queue:
            return None
        return self.queue.pop(0)

    def get_consumer(self, app, **options):
        return self.DummyConsumer(self)

    @contextmanager
    def get_publisher(self, app, **options):
        yield self.DummyPublisher(self)


class CeleryTestMixIn(object):

    # set this to RabbitConsumerFactory to send Vumi API
    # commands over real RabbitMQ
    VUMI_COMMANDS_CONSUMER = DummyConsumerFactory

    def setup_celery_for_tests(self):
        """Setup celery for tests."""
        celery_config = os.environ.get("CELERY_CONFIG_MODULE")
        os.environ["CELERY_CONFIG_MODULE"] = "celery.tests.config"
        self._app = app_or_default()
        always_eager = self._app.conf.CELERY_ALWAYS_EAGER
        self._app.conf.CELERY_ALWAYS_EAGER = True
        self._old_celery = celery_config, always_eager
        self._consumer_factory = self.VUMI_COMMANDS_CONSUMER()

    def restore_celery(self):
        self._consumer_factory.teardown()
        celery_config, always_eager = self._old_celery
        if celery_config is None:
            del os.environ["CELERY_CONFIG_MODULE"]
        else:
            os.environ["CELERY_CONFIG_MODULE"] = celery_config
        self._app.conf.CELERY_ALWAYS_EAGER = always_eager

    def get_consumer(self, **options):
        """Create a command message consumer.

        Call this *before* sending any messages otherwise your
        tests will fail when run against real RabbitMQ because:

        * Messages sent to non-existent consumers will be lost.
        * RabbitConsumerFactory clears out any remaining commands
          from old test runs before returning the consumer.
        """
        return self._consumer_factory.get_consumer(self._app, **options)

    def get_cmd_consumer(self):
        return self.get_consumer(**VumiApiCommand.default_routing_config())

    def fetch_cmds(self, consumer):
        msgs = []
        while True:
            msg = consumer.fetch()
            if msg is not None:
                msgs.append(msg.payload)
            else:
                break
        return [VumiApiCommand(**payload) for payload in msgs]


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
        # have properties set. Therefore, we find all account keys and clear
        # properties from their associated buckets.
        accounts = yield self._list_accounts(manager)
        yield manager.purge_all()
        # This must happen after the objects are deleted, otherwise the indexes
        # don't go away.
        yield self._clear_bucket_properties(accounts, manager)

    def mk_config(self, config):
        config = super(GoPersistenceMixin, self).mk_config(config)
        config.setdefault('metrics_prefix', type(self).__module__)
        return config

    @PersistenceMixin.sync_or_async
    def mk_user(self, vumi_api, username):
        key = "test-%s-user" % (self._users_created,)
        self._users_created += 1
        user = vumi_api.account_store.users(key, username=username)
        yield user.save()
        returnValue(user)


class GoAppWorkerTestMixin(GoPersistenceMixin):

    def _worker_name(self):
        # DummyApplicationWorker has no worker_name attr.
        return getattr(self.application_class, 'worker_name', 'unnamed')

    def _conversation_type(self):
        # This is a guess based on worker_name.
        # We need a better way to do this.
        return self._worker_name().rpartition('_')[0].decode('utf-8')

    def _command_rkey(self):
        return "%s.control" % (self._worker_name(),)

    def setup_tagpools(self):
        return self.setup_tagpool(u"pool", [u"tag1", u"tag2"])

    @inlineCallbacks
    def setup_tagpool(self, pool, tags, transport_name=None, permission=True):
        tags = [(pool, tag) for tag in tags]
        if transport_name is None:
            transport_name = self.transport_name
        yield self.vumi_api.tpm.declare_tags(tags)
        yield self.vumi_api.tpm.set_metadata(pool, {
            "transport_type": self.transport_type,
            "transport_name": transport_name,
        })
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

    @inlineCallbacks
    def create_conversation(self, **kw):
        conv_type = kw.pop('conversation_type', None)
        if conv_type is None:
            conv_type = self._conversation_type()
        name = kw.pop('name', u'Subject')
        description = kw.pop('description', u'')
        config = kw.pop('config', {})
        self.assertTrue(isinstance(config, dict))
        conversation = yield self.user_api.new_conversation(
            conv_type, name, description, config, **kw)
        returnValue(self.user_api.wrap_conversation(conversation))

    @inlineCallbacks
    def start_conversation(self, conversation, *args, **kwargs):
        old_cmds = len(self.get_dispatcher_commands())
        yield conversation.start(*args, **kwargs)
        for cmd in self.get_dispatcher_commands()[old_cmds:]:
            yield self.dispatch_command(
                cmd.payload['command'], *cmd.payload['args'],
                **cmd.payload['kwargs'])

    def poll_metrics(self, assert_prefix=None, app=None):
        if app is None:
            app = self.app
        values = {}
        if assert_prefix is not None:
            assert_prefix += '.'
        for name, metric in app.metrics._metrics_lookup.items():
            if assert_prefix is not None:
                self.assertTrue(name.startswith(assert_prefix))
                name = name[len(assert_prefix):]
            values[name] = [v for _, v in metric.poll()]
        return values

    def dispatch_to_conv(self, msg, conv):
        conv.set_go_helper_metadata(msg['helper_metadata'])
        return self.dispatch(msg)

    def store_outbound_msg(self, msg, conv=None, batch_id=None):
        if batch_id is None and conv is not None:
            [batch_id] = conv.get_batch_keys()
        return self.user_api.api.mdb.add_outbound_message(
            msg, batch_id=batch_id)

    def store_inbound_msg(self, msg, conv=None, batch_id=None):
        if batch_id is None and conv is not None:
            [batch_id] = conv.get_batch_keys()
        return self.user_api.api.mdb.add_inbound_message(
            msg, batch_id=batch_id)


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
        if hasattr(worker, 'vumi_api'):
            self._persist_riak_managers.append(worker.vumi_api.manager)
            self._persist_redis_managers.append(worker.vumi_api.redis)
        returnValue(worker)
