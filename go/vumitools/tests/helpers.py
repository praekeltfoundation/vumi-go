from datetime import datetime, timedelta
import uuid

from twisted.internet.defer import (
    inlineCallbacks, returnValue, Deferred, gatherResults)
from twisted.python.monkey import MonkeyPatcher

from zope.interface import implements

from vumi.tests.helpers import (
    WorkerHelper, MessageHelper, PersistenceHelper, maybe_async, proxyable,
    generate_proxies, IHelper, maybe_async_return)

import go.config
from go.vumitools.api import (
    VumiApi, VumiApiEvent, VumiApiCommand, ApiCommandPublisher)
from go.vumitools.api_worker import EventDispatcher
from go.vumitools.routing import RoutingMetadata
from go.vumitools.utils import MessageMetadataHelper


class PatchHelper(object):
    implements(IHelper)

    def __init__(self):
        self._monkey_patches = []

    def setup(self):
        pass

    def cleanup(self):
        for patch in reversed(self._monkey_patches):
            patch.restore()

    @proxyable
    def monkey_patch(self, obj, attribute, value):
        monkey_patch = MonkeyPatcher((obj, attribute, value))
        self._monkey_patches.append(monkey_patch)
        monkey_patch.patch()
        return monkey_patch

    @proxyable
    def patch_config(self, **kwargs):
        for key, value in kwargs.items():
            self.monkey_patch(go.config, "_%s" % key, value)


class GoMessageHelper(object):
    implements(IHelper)

    def __init__(self, vumi_helper=None, **kw):
        self._msg_helper = MessageHelper(**kw)
        self.transport_name = self._msg_helper.transport_name
        self._vumi_helper = vumi_helper

    def setup(self):
        pass

    def cleanup(self):
        return self._msg_helper.cleanup()

    def _get_opms(self):
        if self._vumi_helper is None:
            raise ValueError("No message store provided.")
        return self._vumi_helper.get_vumi_api().get_operational_message_store()

    @proxyable
    def add_router_metadata(self, msg, router):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(None, msg)
        md.set_router_info(router.router_type, router.key)
        md.set_user_account(router.user_account.key)

    @proxyable
    def add_conversation_metadata(self, msg, conv):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(None, msg)
        md.set_conversation_info(conv.conversation_type, conv.key)
        md.set_user_account(conv.user_account.key)

    @proxyable
    def add_tag_metadata(self, msg, tag):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(None, msg)
        md.set_tag(tag)

    @proxyable
    def _add_go_metadata(self, msg, conv, router):
        if conv is not None:
            self.add_conversation_metadata(msg, conv)
        if router is not None:
            self.add_router_metadata(msg, router)

    @proxyable
    def _add_go_routing_metadata(self, msg, hops, outbound_hops):
        rmeta = RoutingMetadata(msg)
        if hops is not None:
            rmeta.set_hops(hops)
        if outbound_hops is not None:
            rmeta.set_outbound_hops(outbound_hops)

    @proxyable
    def make_inbound(self, content, conv=None, router=None,
                     hops=None, outbound_hops=None, tag=None, **kw):
        msg = self._msg_helper.make_inbound(content, **kw)
        self._add_go_metadata(msg, conv, router)
        self._add_go_routing_metadata(msg, hops, outbound_hops)
        if tag is not None:
            self.add_tag_metadata(msg, tag)
        return msg

    @proxyable
    def make_outbound(self, content, conv=None, router=None,
                      hops=None, outbound_hops=None, tag=None, **kw):
        msg = self._msg_helper.make_outbound(content, **kw)
        self._add_go_metadata(msg, conv, router)
        self._add_go_routing_metadata(msg, hops, outbound_hops)
        if tag is not None:
            self.add_tag_metadata(msg, tag)
        return msg

    @proxyable
    def make_ack(self, msg=None, conv=None, router=None,
                 hops=None, outbound_hops=None, **kw):
        ack = self._msg_helper.make_ack(msg, **kw)
        self._add_go_metadata(ack, conv, router)
        self._add_go_routing_metadata(ack, hops, outbound_hops)
        return ack

    @proxyable
    def make_nack(self, msg=None, conv=None, router=None,
                  hops=None, outbound_hops=None, **kw):
        nack = self._msg_helper.make_nack(msg, **kw)
        self._add_go_metadata(nack, conv, router)
        self._add_go_routing_metadata(nack, hops, outbound_hops)
        return nack

    @proxyable
    def make_delivery_report(self, msg=None, conv=None, router=None,
                             hops=None, outbound_hops=None, **kw):
        dr = self._msg_helper.make_delivery_report(msg, **kw)
        self._add_go_metadata(dr, conv, router)
        self._add_go_routing_metadata(dr, hops, outbound_hops)
        return dr

    @proxyable
    def make_reply(self, msg, content, **kw):
        return self._msg_helper.make_reply(msg, content, **kw)

    @proxyable
    def store_inbound(self, conv, msg):
        return self._get_opms().add_inbound_message(
            msg, batch_ids=[conv.batch.key])

    @proxyable
    def store_outbound(self, conv, msg):
        return self._get_opms().add_outbound_message(
            msg, batch_ids=[conv.batch.key])

    @proxyable
    def store_event(self, conv, event):
        return self._get_opms().add_event(event, batch_ids=[conv.batch.key])

    @proxyable
    def make_stored_inbound(self, conv, content, **kw):
        msg = self.make_inbound(content, conv=conv, **kw)
        return maybe_async_return(msg, self.store_inbound(conv, msg))

    @proxyable
    def make_stored_outbound(self, conv, content, **kw):
        msg = self.make_outbound(content, conv=conv, **kw)
        return maybe_async_return(msg, self.store_outbound(conv, msg))

    @proxyable
    def make_stored_ack(self, conv, msg, **kw):
        event = self.make_ack(msg, conv=conv, **kw)
        return maybe_async_return(event, self.store_event(conv, event))

    @proxyable
    def make_stored_nack(self, conv, msg, **kw):
        event = self.make_nack(msg, conv=conv, **kw)
        return maybe_async_return(event, self.store_event(conv, event))

    @proxyable
    def make_stored_delivery_report(self, conv, msg, **kw):
        event = self.make_delivery_report(msg, conv=conv, **kw)
        return maybe_async_return(event, self.store_event(conv, event))

    @proxyable
    def add_inbound_to_conv(self, conv, count, start_date=None,
                            time_multiplier=10):
        now = start_date or datetime.now().date()

        messages = []
        for i in range(count):
            timestamp = now - timedelta(hours=i * time_multiplier)
            messages.append(self.make_stored_inbound(
                conv, "inbound %s" % (i,), from_addr='from-%s' % (i,),
                timestamp=timestamp))
        # We can't use `maybe_async_return` here because we need gatherResults.
        if isinstance(messages[0], Deferred):
            return gatherResults(messages)
        else:
            return messages

    @proxyable
    def add_outbound_to_conv(self, conv, count, start_date=None,
                             time_multiplier=10):
        now = start_date or datetime.now().date()

        messages = []
        for i in range(count):
            timestamp = now - timedelta(hours=i * time_multiplier)
            messages.append(self.make_stored_outbound(
                conv, "outbound %s" % (i,), to_addr='to-%s' % (i,),
                timestamp=timestamp))
        # We can't use `maybe_async_return` here because we need gatherResults.
        if isinstance(messages[0], Deferred):
            return gatherResults(messages)
        else:
            return messages

    @proxyable
    def add_replies_to_conv(self, conv, msgs):
        messages = []
        ds = []
        for msg in msgs:
            timestamp = msg['timestamp'] + timedelta(seconds=1)
            reply = self.make_reply(msg, "reply", timestamp=timestamp)
            messages.append(reply)
            ds.append(self.store_outbound(conv, reply))
        # We can't use `maybe_async_return` here because we need gatherResults.
        if isinstance(ds[0], Deferred):
            return gatherResults(ds).addCallback(lambda r: messages)
        else:
            return messages


class FakeAmqpConnection(object):
    """Wrapper around an AMQP client that forwards messages.

    Command and metric messages are stored for later inspection.
    """
    def __init__(self, amqp_client):
        self._amqp = amqp_client
        self._connected = False
        self.commands = []
        self.metrics = []

    def is_connected(self):
        return self._connected

    def connect(self, dsn=None):
        self._connected = True

    def publish(self, message, exchange, routing_key):
        self._amqp.publish_raw(exchange, routing_key, message)

    def publish_command_message(self, command):
        self.commands.append(command)
        self.publish(command.to_json(), 'vumi', 'vumi.api')

    def publish_metric_message(self, metric):
        self.metrics.append(metric)
        self.publish(metric.to_json(), 'vumi', 'vumi.metrics')

    def get_commands(self):
        commands, self.commands = self.commands, []
        return commands

    def get_metrics(self):
        metrics, self.metrics = self.metrics, []
        return metrics

    def get_metric_publisher(self):
        from go.base.amqp import MetricPublisher
        return MetricPublisher(self)


class VumiApiHelper(object):
    # TODO: Clear bucket properties.
    #       We need two things for this:
    #        * The ability to clear bucket properties in our Riak layer.
    #        * Tracking accounts created so we know which buckets to clear.
    #
    #       The first needs to happen in vumi and requires an updated Riak
    #       client. The second isn't really worth doing unitl the first is
    #       done.

    implements(IHelper)

    def __init__(self, is_sync=False, use_riak=True):
        self.is_sync = is_sync
        self._patch_helper = PatchHelper()
        generate_proxies(self, self._patch_helper)

        self._persistence_helper = PersistenceHelper(
            use_riak=use_riak, is_sync=is_sync)
        self.broker = None  # Will be replaced by the first worker_helper.
        self._worker_helpers = {}
        self._users_created = 0
        self._user_helpers = {}
        self._vumi_api = None
        self._cleanup_vumi_api = False

        generate_proxies(self, self._persistence_helper)

    def setup(self, setup_vumi_api=True):
        self._persistence_helper.setup()
        if self.is_sync:
            self._django_amqp_setup()
        if setup_vumi_api:
            return self.setup_vumi_api()

    @maybe_async
    def cleanup(self):
        for worker_helper in self._worker_helpers.values():
            # All of these will wait for the same broker, but that's fine.
            yield worker_helper.cleanup()
        if self._cleanup_vumi_api:
            yield self._vumi_api.close()
        yield self._persistence_helper.cleanup()
        self._patch_helper.cleanup()

    def _django_amqp_setup(self):
        import go.base.amqp
        import go.base.utils
        # We might need an AMQP connection at some point.
        broker = self.get_worker_helper().broker
        broker.exchange_declare('vumi', 'direct')
        self.django_amqp_connection = FakeAmqpConnection(broker)
        self.monkey_patch(
            go.base.utils, 'connection', self.django_amqp_connection)
        self.monkey_patch(
            go.base.amqp, 'connection', self.django_amqp_connection)

    def get_worker_helper(self, connector_name=None):
        if connector_name not in self._worker_helpers:
            worker_helper = WorkerHelper(connector_name, self.broker)
            # If this is our first worker helper, we need to grab the broker it
            # created. If it isn't, its broker will be self.broker anyway.
            self.broker = worker_helper.broker
            self._worker_helpers[connector_name] = worker_helper
        return self._worker_helpers[connector_name]

    @proxyable
    def get_vumi_api(self):
        assert self._vumi_api is not None, "No vumi_api provided."
        return self._vumi_api

    @proxyable
    def set_vumi_api(self, vumi_api):
        assert self._vumi_api is None, "Can't override existing vumi_api."
        self._vumi_api = vumi_api
        # TODO: Find a nicer way to give everything the same fake redis.
        pcfg = self._persistence_helper._config_overrides
        pcfg['redis_manager']['FAKE_REDIS'] = vumi_api.redis

    @proxyable
    def setup_vumi_api(self):
        # If we create our own VumiApi, we need to clean it up.
        self._cleanup_vumi_api = True
        if self.is_sync:
            return self.setup_sync_vumi_api()
        else:
            return self.setup_async_vumi_api()

    def setup_sync_vumi_api(self):
        from django.conf import settings
        import go.base.amqp
        self._vumi_api = VumiApi.from_config_sync(
            settings.VUMI_API_CONFIG, go.base.amqp.connection)

    def setup_async_vumi_api(self):
        worker_helper = self.get_worker_helper()
        amqp_client = worker_helper.get_fake_amqp_client(worker_helper.broker)
        d = amqp_client.start_publisher(ApiCommandPublisher)
        d.addCallback(lambda cmd_publisher: VumiApi.from_config_async(
            self.mk_config({}), cmd_publisher))
        return d.addCallback(self.set_vumi_api)

    @proxyable
    @maybe_async
    def make_user(self, username, enable_search=True, django_user_pk=None):
        # NOTE: We use bytes instead of unicode here because that's what the
        #       real new_user gives us.
        key = "test-%s-user" % (len(self._user_helpers),)
        user = self.get_vumi_api().account_store.users(key, username=username)
        yield user.save()
        user_helper = UserApiHelper(self, key, django_user_pk=django_user_pk)
        self._user_helpers[key] = user_helper
        if enable_search:
            contact_store = user_helper.user_api.contact_store
            yield contact_store.contacts.enable_search()
            yield contact_store.groups.enable_search()
        returnValue(self.get_user_helper(user.key))

    @proxyable
    def get_user_helper(self, account_key):
        return self._user_helpers[account_key]

    @proxyable
    @maybe_async
    def get_or_create_user(self):
        assert len(self._user_helpers) <= 1, "Too many users."
        if not self._user_helpers:
            yield self.make_user(u"testuser")
        returnValue(self._user_helpers.values()[0])

    @proxyable
    @maybe_async
    def setup_tagpool(self, pool, tags, metadata=None):
        tags = [(pool, tag) for tag in tags]
        yield self.get_vumi_api().tpm.declare_tags(tags)
        if metadata:
            yield self.get_vumi_api().tpm.set_metadata(pool, metadata)
        returnValue(tags)

    def get_dispatched_commands(self):
        return self.get_worker_helper().get_dispatched(
            'vumi', 'api', VumiApiCommand)


class UserApiHelper(object):
    implements(IHelper)

    def __init__(self, vumi_helper, account_key, django_user_pk=None):
        self.is_sync = vumi_helper.is_sync
        self._vumi_helper = vumi_helper
        self.account_key = account_key
        self.user_api = vumi_helper.get_vumi_api().get_user_api(account_key)

        # For use in get_django_user, if applicable.
        self._django_user_pk = django_user_pk

        # Easier access to these stores is useful.
        self.contact_store = self.user_api.contact_store

    def setup(self):
        pass

    def cleanup(self):
        pass

    @proxyable
    def get_user_account(self):
        return self.user_api.get_user_account()

    def get_django_user(self):
        if self._django_user_pk is None:
            raise RuntimeError("get_django_user() only works in Django-land.")
        from django.contrib.auth import get_user_model
        return get_user_model().objects.get(pk=self._django_user_pk)

    @proxyable
    @maybe_async
    def add_tagpool_permission(self, tagpool, max_keys=None):
        # TODO: Move this into the API rather than the test helper.
        permission = yield self.user_api.api.account_store.tag_permissions(
            uuid.uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        yield permission.save()
        account = yield self.get_user_account()
        account.tagpools.add(permission)
        yield account.save()

    @proxyable
    @maybe_async
    def add_app_permission(self, application):
        # TODO: Move this into the API rather than the test helper.
        account_store = self.user_api.api.account_store
        permission = account_store.application_permissions(
            uuid.uuid4().hex, application=application)
        yield permission.save()

        account = yield self.get_user_account()
        account.applications.add(permission)
        yield account.save()

    @proxyable
    @maybe_async
    def create_conversation(self, conversation_type, started=False,
                            archived=False, **kw):
        name = kw.pop('name', u'My Conversation')
        description = kw.pop('description', u'')
        config = kw.pop('config', {})
        assert isinstance(config, dict)
        if started:
            kw.setdefault('status', u'running')
        if archived:
            kw.setdefault('archive_status', u'archive')
        conversation = yield self.user_api.new_conversation(
            conversation_type, name, description, config, **kw)
        returnValue(self.user_api.wrap_conversation(conversation))

    @proxyable
    def create_router(self, router_type, started=False, **kw):
        name = kw.pop('name', u'My Router')
        description = kw.pop('description', u'')
        config = kw.pop('config', {})
        assert isinstance(config, dict)
        if started:
            kw.setdefault('status', u'running')
        return self.user_api.new_router(
            router_type, name, description, config, **kw)

    @proxyable
    def get_conversation(self, conversation_key):
        return self.user_api.get_wrapped_conversation(conversation_key)

    @proxyable
    def get_router(self, router_key):
        return self.user_api.get_router(router_key)


class EventHandlerHelper(object):
    # TODO: This class probably doesn't belong here, but there isn't really
    #       anywhere better to put it. It needs to be available to
    #       go.vumitools.tests.test_handler as well as various event handler
    #       tests in go.apps.
    implements(IHelper)

    def __init__(self):
        self.vumi_helper = VumiApiHelper()
        self.worker_helper = self.vumi_helper.get_worker_helper()

    def setup(self):
        return self.vumi_helper.setup(setup_vumi_api=False)

    def cleanup(self):
        return self.vumi_helper.cleanup()

    @inlineCallbacks
    def setup_event_dispatcher(self, name, cls, config):
        # TODO: Remove the `transport_name` field from the config below when
        #       EventDispatcher is no longer an ApplicationWorker subclass.
        app_config = self.vumi_helper.mk_config({
            'event_handlers': {
                name: "%s.%s" % (cls.__module__, cls.__name__),
            },
            name: config,
            'transport_name': 'sphex',
        })

        self.event_dispatcher = yield self.worker_helper.get_worker(
            EventDispatcher, app_config)
        self.vumi_helper.set_vumi_api(self.event_dispatcher.vumi_api)

        self.user_helper = yield self.vumi_helper.make_user(u'acct')
        yield self.vumi_helper.setup_tagpool(u"pool", [u"tag1", u"tag2"])
        yield self.user_helper.add_tagpool_permission(u"pool")
        self.conversation = yield self.user_helper.create_conversation(
            u'bulk_message')

    def get_handler(self, name):
        return self.event_dispatcher.handlers[name]

    def track_event(self, event_type, handler_name, handler_config={}):
        handler_configs = self.event_dispatcher.account_handler_configs
        account_handlers = handler_configs.setdefault(
            self.user_helper.account_key, [])

        account_handlers.append([
            [self.conversation.key, event_type], [
                [handler_name, handler_config]
            ]
        ])

    def make_event(self, event_type, content):
        return VumiApiEvent.event(
            self.user_helper.account_key, self.conversation.key,
            event_type, content)

    def dispatch_event(self, event):
        return self.worker_helper.dispatch_raw('vumi.event', event)

    def get_dispatched_commands(self):
        return self.vumi_helper.get_dispatched_commands()
