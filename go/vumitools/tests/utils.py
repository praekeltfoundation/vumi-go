# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

import os
from contextlib import contextmanager

from twisted.python. monkey import MonkeyPatcher
from celery.app import app_or_default

from go.vumitools.api import VumiApiCommand
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.bulk_send_application import BulkSendApplication
from vumi.message import TransportUserMessage
from vumi.tests.utils import get_stubbed_worker


# class DummyApiWorker(CommandDispatcher):

#     def send_to(self, to_addr, content, **msg_options):
#         msg_options.setdefault('transport_name', 'dummy_transport')
#         msg_options.setdefault('transport_type', 'sms')
#         return TransportUserMessage(to_addr=to_addr, content=content,
#                                     **msg_options)


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

    def process_cmds(self, store, cmds=None, consumer=None):
        """Create a stubby Vumi API worker and feed commands to it."""
        assert ((cmds is None) ^ (consumer is None))
        if cmds is None:
            cmds = self.fetch_cmds(consumer)

        command_dispatch_worker = get_stubbed_worker(CommandDispatcher, {
            'transport_name': 'dummy_transport',
            'worker_names': ['bulk_message_application']
        })

        bulk_message_app_worker = get_stubbed_worker(BulkSendApplication, {
            'transport_name': 'bulk_message_transport',
            'worker_name': 'bulk_message_application',
            'send_to': {
                'default': {
                    'transport_name': "invalid broken transport"
                }
            }
        })

        def _consume_api_commands(*args, **kwargs):
            command_dispatch_worker.store = store
            for cmd in cmds:
                command_dispatch_worker.consume_api_command(cmd)


        d = command_dispatch_worker.startWorker()
        d.addCallback(lambda *a, **kw: bulk_message_app_worker.startWorker())
        d.addCallback(_consume_api_commands)
