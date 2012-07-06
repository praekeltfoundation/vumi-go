# -*- test-case-name: go.apps.opt_out.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

import os
from contextlib import contextmanager

from twisted.python.monkey import MonkeyPatcher
from twisted.internet.defer import DeferredList, inlineCallbacks
from celery.app import app_or_default

from vumi.persist.fields import ForeignKeyProxy, ManyToManyProxy, DynamicProxy
from vumi.message import TransportUserMessage
from vumi.persist import txriak_manager

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

    def mkmsg_in(self, content, **kw):
        kw.setdefault('to_addr', '+123')
        kw.setdefault('from_addr', '+456')
        kw.setdefault('transport_name', 'dummy_transport')
        kw.setdefault('transport_type', 'sms')
        return TransportUserMessage(content=content, **kw)

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


class RiakTestMixin(object):
    def get_riak_manager(self, config):
        riak_manager = txriak_manager.TxRiakManager.from_config(config)
        self._riak_managers.append(riak_manager)
        return riak_manager

    def riak_setup(self):
        self._riak_managers = []

    def _clear_bucket_properties(self, manager):
        if not hasattr(txriak_manager, 'delete_bucket_properties'):
            # This doesn't exist everywhere yet.
            return

        # If buckets are empty, they aren't listed. However, they may still
        # have properties set.
        client = manager.client

        def delete_props(key):
            sub_manager = manager.sub_manager(key)
            return DeferredList([
                    txriak_manager.delete_bucket_properties(
                        client.bucket(sub_manager.bucket_name(Contact))),
                    txriak_manager.delete_bucket_properties(
                        client.bucket(sub_manager.bucket_name(ContactGroup))),
                    ])

        def clear_accounts(keys):
            return DeferredList([delete_props(key) for key in keys])

        d = client.bucket(manager.bucket_name(UserAccount)).list_keys()
        d.addCallback(clear_accounts)
        return d

    @inlineCallbacks
    def _purge_manager(self, manager):
        yield self._clear_bucket_properties(manager)
        yield manager.purge_all()

    @inlineCallbacks
    def riak_teardown(self):
        for manager in self._riak_managers:
            yield self._purge_manager(manager)
