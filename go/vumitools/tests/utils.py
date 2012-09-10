# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

import os
from contextlib import contextmanager
import json

from twisted.python.monkey import MonkeyPatcher
from twisted.internet.defer import inlineCallbacks, returnValue
from celery.app import app_or_default

from vumi.persist.fields import ForeignKeyProxy, ManyToManyProxy, DynamicProxy
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


def dummy_consumer_factory_factory_factory(publish_func):
    def dummy_consumer_factory_factory():
        dummy_consumer_factory = DummyConsumerFactory()
        dummy_consumer_factory.publish = publish_func
        return dummy_consumer_factory
    return dummy_consumer_factory_factory


class AppWorkerTestCase(GoPersistenceMixin, CeleryTestMixIn,
                        ApplicationTestCase):
    override_dummy_consumer = True

    @inlineCallbacks
    def setUp(self):
        yield super(AppWorkerTestCase, self).setUp()
        if self.override_dummy_consumer:
            self.VUMI_COMMANDS_CONSUMER = (
                dummy_consumer_factory_factory_factory(self.publish_command))
        self.setup_celery_for_tests()

    @inlineCallbacks
    def tearDown(self):
        self.restore_celery()
        yield super(AppWorkerTestCase, self).tearDown()

    def publish_command(self, cmd_dict):
        data = json.dumps(cmd_dict)
        self._amqp.publish_raw('vumi', 'vumi.api', data)

    def get_dispatcher_commands(self):
        return self._amqp.get_messages('vumi', 'vumi.api')

    def get_bulk_message_commands(self):
        return self._amqp.get_messages('vumi',
                                       "%s.control" % self.app.worker_name)

    def get_dispatched_app_events(self):
        return self._amqp.get_messages('vumi', 'vumi.event')

    def publish_event(self, **kw):
        event = TransportEvent(**kw)
        d = self.dispatch(event, rkey=self.rkey('event'))
        d.addCallback(lambda _result: event)
        return d

    @inlineCallbacks
    def get_application(self, *args, **kw):
        worker = yield super(AppWorkerTestCase, self).get_application(
            *args, **kw)
        if hasattr(worker, 'manager'):
            self._persist_riak_managers.append(worker.manager)
        if hasattr(worker, 'redis'):
            self._persist_redis_managers.append(worker.redis)
        returnValue(worker)
