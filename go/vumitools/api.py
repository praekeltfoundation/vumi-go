# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Convenience API, mostly for working with various datastores."""

from uuid import uuid4
from collections import defaultdict

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.blinkenlights.metrics import MetricManager
from vumi.errors import VumiError
from vumi.message import Message
from vumi.components.tagpool import TagpoolManager
from vumi.components.message_store import MessageStore
from vumi.persist.model import Manager
from vumi.persist.riak_manager import RiakManager
from vumi.persist.txriak_manager import TxRiakManager
from vumi.persist.redis_manager import RedisManager
from vumi.persist.txredis_manager import TxRedisManager
from vumi.service import Publisher
from vumi import log

from go.config import configured_conversations, configured_routers
from go.vumitools.account import AccountStore
from go.vumitools.channel import ChannelStore
from go.vumitools.contact import ContactStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.opt_out import OptOutStore
from go.vumitools.router import RouterStore
from go.vumitools.conversation.utils import ConversationWrapper
from go.vumitools.token_manager import TokenManager

from vumi.message import TransportUserMessage


class TagpoolSet(object):
    """Holder for helper methods for retrieving tag pool information.

    :param dict pools:
        Dictionary of `tagpool name` -> `tagpool metadata` mappings.
    """

    # TODO: this should ideally need to be moved somewhere else
    #       but it's purely cosmetic so it can live here for now
    _DELIVERY_CLASS_NAMES = {
        'sms': 'SMS',
        'ussd': 'USSD',
        'gtalk': 'Gtalk',
        }

    def __init__(self, pools):
        self._pools = pools

    def pools(self):
        return self._pools.keys()

    def display_name(self, pool):
        return self._pools[pool].get('display_name', pool)

    def country_name(self, pool, default):
        return self._pools[pool].get('country_name', default)

    def user_selects_tag(self, pool):
        return self._pools[pool].get('user_selects_tag', False)

    def delivery_class(self, pool):
        return self._pools[pool].get('delivery_class', None)

    def delivery_classes(self):
        classes = set(self.delivery_class(pool) for pool in self.pools())
        classes.discard(None)
        return list(classes)

    def delivery_class_name(self, delivery_class):
        return self._DELIVERY_CLASS_NAMES.get(delivery_class, delivery_class)


class VumiUserApi(object):

    conversation_wrapper = ConversationWrapper

    def __init__(self, api, user_account_key, cleanup_api=False):
        # We could get either bytes or unicode here. Decode if necessary.
        if not isinstance(user_account_key, unicode):
            user_account_key = user_account_key.decode('utf8')
        self.api = api
        self.manager = self.api.manager
        self.user_account_key = user_account_key
        self._cleanup_api = cleanup_api
        self.conversation_store = ConversationStore(self.api.manager,
                                                    self.user_account_key)
        self.contact_store = ContactStore(self.api.manager,
                                          self.user_account_key)
        self.router_store = RouterStore(self.api.manager,
                                        self.user_account_key)
        self.channel_store = ChannelStore(self.api.manager,
                                          self.user_account_key)
        self.optout_store = OptOutStore(self.api.manager,
                                        self.user_account_key)

    @Manager.calls_manager
    def close(self):
        if self._cleanup_api:
            yield self.api.close()

    def exists(self):
        return self.api.user_exists(self.user_account_key)

    @classmethod
    def from_config_sync(cls, user_account_key, config):
        return cls(
            VumiApi.from_config_sync(config), user_account_key,
            cleanup_api=True)

    @classmethod
    def from_config_async(cls, user_account_key, config):
        d = VumiApi.from_config_async(config)
        return d.addCallback(cls, user_account_key, cleanup_api=True)

    def get_user_account(self):
        return self.api.get_user_account(self.user_account_key)

    def wrap_conversation(self, conversation):
        """Wrap a conversation with a ConversationWrapper.

        What it says on the tin, really.

        :param Conversation conversation:
            Conversation object to wrap.
        :rtype:
            ConversationWrapper.
        """
        return self.conversation_wrapper(conversation, self)

    @Manager.calls_manager
    def get_wrapped_conversation(self, conversation_key):
        conversation = yield self.conversation_store.get_conversation_by_key(
            conversation_key)
        if conversation:
            returnValue(self.wrap_conversation(conversation))

    def get_conversation(self, conversation_key):
        return self.conversation_store.get_conversation_by_key(
            conversation_key)

    def get_router(self, router_key):
        return self.router_store.get_router_by_key(router_key)

    @Manager.calls_manager
    def get_channel(self, tag):
        tagpool_meta = yield self.api.tpm.get_metadata(tag[0])
        tag_info = yield self.api.mdb.get_tag_info(tag)
        channel = yield self.channel_store.get_channel_by_tag(
            tag, tagpool_meta, tag_info.current_batch.key)
        returnValue(channel)

    @Manager.calls_manager
    def archived_conversations(self):
        conv_store = self.conversation_store
        keys = yield conv_store.list_conversations()
        conversations = []
        for bunch in conv_store.conversations.load_all_bunches(keys):
            conversations.extend((yield bunch))
        returnValue([c for c in conversations if c.archived()])

    @Manager.calls_manager
    def active_conversations(self):
        keys = yield self.conversation_store.list_active_conversations()
        # NOTE: This assumes that we don't have very large numbers of active
        #       conversations.
        convs = []
        for convs_bunch in self.conversation_store.load_all_bunches(keys):
            convs.extend((yield convs_bunch))
        returnValue(convs)

    @Manager.calls_manager
    def running_conversations(self):
        keys = yield self.conversation_store.list_running_conversations()
        # NOTE: This assumes that we don't have very large numbers of active
        #       conversations.
        convs = []
        for convs_bunch in self.conversation_store.load_all_bunches(keys):
            convs.extend((yield convs_bunch))
        returnValue(convs)

    @Manager.calls_manager
    def draft_conversations(self):
        # TODO: This should probably be `stopped_conversations` instead, but we
        #       still apparently use `draft` in the UI in places.
        conversations = yield self.active_conversations()
        returnValue([c for c in conversations if c.stopped()])

    @Manager.calls_manager
    def active_routers(self):
        keys = yield self.router_store.list_active_routers()
        # NOTE: This assumes that we don't have very large numbers of active
        #       routers.
        routers = []
        for routers_bunch in self.router_store.load_all_bunches(keys):
            routers.extend((yield routers_bunch))
        returnValue(routers)

    @Manager.calls_manager
    def archived_routers(self):
        conv_store = self.router_store
        keys = yield conv_store.list_routers()
        routers = []
        for bunch in conv_store.routers.load_all_bunches(keys):
            routers.extend((yield bunch))
        returnValue([r for r in routers if r.archived()])

    @Manager.calls_manager
    def active_channels(self):
        channels = []
        user_account = yield self.get_user_account()
        for tag in user_account.tags:
            channel = yield self.get_channel(tuple(tag))
            channels.append(channel)
        returnValue(channels)

    @Manager.calls_manager
    def tagpools(self):
        user_account = yield self.get_user_account()

        tp_usage = defaultdict(int)
        for tag in user_account.tags:
            tp_usage[tag[0]] += 1

        all_pools = yield self.api.tpm.list_pools()
        allowed_pools = set()
        for tp_bunch in user_account.tagpools.load_all_bunches():
            for tp in (yield tp_bunch):
                if (tp.max_keys is None
                        or tp.max_keys > tp_usage[tp.tagpool]):
                    allowed_pools.add(tp.tagpool)

        available_pools = []
        for pool in all_pools:
            if pool not in allowed_pools:
                continue
            free_tags = yield self.api.tpm.free_tags(pool)
            if free_tags:
                available_pools.append(pool)

        returnValue((yield self.api.tagpool_set(available_pools)))

    @Manager.calls_manager
    def applications(self):
        user_account = yield self.get_user_account()
        # NOTE: This assumes that we don't have very large numbers of
        #       applications.
        app_permissions = []
        for permissions in user_account.applications.load_all_bunches():
            app_permissions.extend((yield permissions))
        applications = [permission.application for permission
                        in app_permissions]
        app_settings = configured_conversations()
        returnValue(dict((application, app_settings[application])
                         for application in applications
                         if application in app_settings))

    @Manager.calls_manager
    def router_types(self):
        # TODO: Permissions.
        yield None
        router_settings = configured_routers()
        returnValue(dict((router_type, router_settings[router_type])
                         for router_type in router_settings))

    def list_groups(self):
        return self.contact_store.list_groups()

    @Manager.calls_manager
    def new_conversation(self, conversation_type, name, description, config,
                         batch_id=None, **fields):
        if not batch_id:
            batch_id = yield self.api.mdb.batch_start(
                tags=[], user_account=self.user_account_key)
        conv = yield self.conversation_store.new_conversation(
            conversation_type, name, description, config, batch_id, **fields)
        returnValue(conv)

    @Manager.calls_manager
    def new_router(self, router_type, name, description, config,
                   batch_id=None, **fields):
        if not batch_id:
            batch_id = yield self.api.mdb.batch_start(
                tags=[], user_account=self.user_account_key)
        router = yield self.router_store.new_router(
            router_type, name, description, config, batch_id, **fields)
        returnValue(router)

    @Manager.calls_manager
    def get_routing_table(self, user_account=None):
        if user_account is None:
            user_account = yield self.get_user_account()
        if user_account.routing_table is None:
            raise VumiError(
                "Routing table missing for account: %s" % (user_account.key,))
        returnValue(user_account.routing_table)

    @Manager.calls_manager
    def validate_routing_table(self, user_account=None):
        """Check that the routing table on this account is valid.

        Currently we just check account ownership of tags and conversations.

        TODO: Cycle detection, if that's even possible. Maybe other stuff.
        TODO: Determine if this is necessary and move it elsewhere if it is.
        """
        if user_account is None:
            user_account = yield self.get_user_account()
        routing_table = yield self.get_routing_table(user_account)
        # We don't care about endpoints here, only connectors.
        routing_connectors = set()
        for src_conn, _src_ep, dst_conn, _dst_ep in routing_table.entries():
            routing_connectors.add(src_conn)
            routing_connectors.add(dst_conn)

        # Checking tags is cheap and easy, so do that first.
        channels = yield self.active_channels()
        for channel in channels:
            channel_conn = channel.get_connector()
            if channel_conn in routing_connectors:
                routing_connectors.remove(channel_conn)

        # Now we run through active conversations to check those.
        convs = yield self.active_conversations()
        for conv in convs:
            conv_conn = conv.get_connector()
            if conv_conn in routing_connectors:
                routing_connectors.remove(conv_conn)

        # And lasting with active routers
        routers = yield self.active_routers()
        for router in routers:
            router_inbound_conn = router.get_inbound_connector()
            if router_inbound_conn in routing_connectors:
                routing_connectors.remove(router_inbound_conn)
            router_outbound_conn = router.get_outbound_connector()
            if router_outbound_conn in routing_connectors:
                routing_connectors.remove(router_outbound_conn)

        if routing_connectors:
            raise VumiError(
                "Routing table contains illegal connector names: %s" % (
                    routing_connectors,))

    @Manager.calls_manager
    def _update_tag_data_for_acquire(self, user_account, tag):
        # The batch we create here gets added to the tag_info and we can fish
        # it out later. When we replace this with proper channel objects we can
        # stash it there like we do with conversations and routers.
        yield self.api.mdb.batch_start([tag], user_account=user_account.key)
        user_account.tags.append(tag)
        tag_info = yield self.api.mdb.get_tag_info(tag)
        tag_info.metadata['user_account'] = user_account.key.decode('utf-8')
        yield tag_info.save()
        yield user_account.save()

    @Manager.calls_manager
    def acquire_tag(self, pool):
        """Acquire a tag from a given tag pool.

        Tags should be held for the duration of a conversation.

        :type pool: str
        :param pool:
            name of the pool to retrieve tags from.
        :rtype:
            The tag acquired or None if no tag was available.
        """
        user_account = yield self.get_user_account()
        if not (yield user_account.has_tagpool_permission(pool)):
            log.warning("Account '%s' trying to access forbidden pool '%s'" % (
                user_account.key, pool))
            returnValue(None)
        tag = yield self.api.tpm.acquire_tag(pool)
        if tag is not None:
            yield self._update_tag_data_for_acquire(user_account, tag)
        returnValue(tag)

    @Manager.calls_manager
    def acquire_specific_tag(self, tag):
        """Acquire a specific tag.

        Tags should be held for the duration of a conversation.

        :type tag: tag tuple
        :param tag:
            The tag to acquire.
        :rtype:
            The tag acquired or None if the tag was not available.
        """
        user_account = yield self.get_user_account()
        if not (yield user_account.has_tagpool_permission(tag[0])):
            log.warning("Account '%s' trying to access forbidden pool '%s'" % (
                user_account.key, tag[0]))
            returnValue(None)
        tag = yield self.api.tpm.acquire_specific_tag(tag)
        if tag is not None:
            yield self._update_tag_data_for_acquire(user_account, tag)
        returnValue(tag)

    @Manager.calls_manager
    def release_tag(self, tag):
        """Release a tag back to the pool it came from.

        Tags should be released only once a conversation is finished.

        :type pool: str
        :param pool:
            name of the pool to return the tag too (must be the same as
            the name of the pool the tag came from).
        :rtype:
            None.
        """
        user_account = yield self.get_user_account()
        try:
            user_account.tags.remove(list(tag))
        except ValueError, e:
            log.error("Tag not allocated to account: %s" % (tag,), e)
        else:
            tag_info = yield self.api.mdb.get_tag_info(tag)
            if 'user_account' in tag_info.metadata:
                del tag_info.metadata['user_account']
            yield tag_info.save()
            # NOTE: This loads and saves the CurrentTag object a second time.
            #       We should probably refactor the message store to make this
            #       less clumsy.
            if tag_info.current_batch.key:
                yield self.api.mdb.batch_done(tag_info.current_batch.key)

            # Clean up routing table entries.
            routing_table = yield self.get_routing_table(user_account)
            routing_table.remove_transport_tag(tag)

            yield user_account.save()
        yield self.api.tpm.release_tag(tag)

    def delivery_class_for_msg(self, msg):
        # Sometimes we need a `delivery_class` but we don't always have (or
        # want) one. This builds one from `msg['transport_type']`.
        return {
            TransportUserMessage.TT_SMS: 'sms',
            TransportUserMessage.TT_USSD: 'ussd',
            TransportUserMessage.TT_XMPP: 'gtalk',
            TransportUserMessage.TT_TWITTER: 'twitter',
            TransportUserMessage.TT_MXIT: 'mxit',
            TransportUserMessage.TT_WECHAT: 'wechat',
        }.get(msg['transport_type'],
              msg['transport_type'])

    def get_router_api(self, router_type, router_key):
        return VumiRouterApi(self, router_type, router_key)


class VumiRouterApi(object):
    def __init__(self, user_api, router_type, router_key):
        self.user_api = user_api
        self.manager = user_api.manager
        self.router_type = router_type
        self.router_key = router_key

    def get_router(self):
        return self.user_api.get_router(self.router_key)

    @Manager.calls_manager
    def archive_router(self, router=None):
        if router is None:
            router = yield self.get_router()
        router.set_status_finished()
        yield router.save()
        yield self._remove_from_routing_table(router)

    @Manager.calls_manager
    def _remove_from_routing_table(self, router):
        """Remove routing entries for this router.
        """
        user_account = yield self.user_api.get_user_account()
        routing_table = yield self.user_api.get_routing_table(user_account)
        routing_table.remove_router(router)
        yield user_account.save()

    @Manager.calls_manager
    def start_router(self, router=None):
        """Send the start command to this router's worker.

        The router is then responsible for processing this message as
        appropriate and handling the state transition.
        """
        if router is None:
            router = yield self.get_router()
        router.set_status_starting()
        yield router.save()
        yield self.dispatch_router_command('start')

    @Manager.calls_manager
    def stop_router(self, router=None):
        """Send the stop command to this router's worker.

        The router is then responsible for processing this message as
        appropriate and handling the state transition.
        """
        if router is None:
            router = yield self.get_router()
        router.set_status_stopping()
        yield router.save()
        yield self.dispatch_router_command('stop')

    def dispatch_router_command(self, command, *args, **kwargs):
        """Send a command to this router's worker.

        :type command: str
        :params command:
            The name of the command to call
        """
        worker_name = '%s_router' % (self.router_type,)
        kwargs.setdefault('user_account_key', self.user_api.user_account_key)
        kwargs.setdefault('router_key', self.router_key)
        return self.user_api.api.send_command(
            worker_name, command, *args, **kwargs)


class VumiApi(object):
    def __init__(self, manager, redis, sender=None, metric_publisher=None):
        # local import to avoid circular import since
        # go.api.go_api needs to access VumiApi
        from go.api.go_api.session_manager import SessionManager

        self.manager = manager
        self.redis = redis

        self.tpm = TagpoolManager(self.redis.sub_manager('tagpool_store'))
        self.mdb = MessageStore(
            self.manager, self.redis.sub_manager('message_store'))
        self.account_store = AccountStore(self.manager)
        self.token_manager = TokenManager(
            self.redis.sub_manager('token_manager'))
        self.session_manager = SessionManager(
            self.redis.sub_manager('session_manager'))
        self.mapi = sender
        self.metric_publisher = metric_publisher

    @Manager.calls_manager
    def close(self):
        """
        Clean up our Redis and Riak managers.

        This method is called `close` rather than `cleanup` so we can use
        `contextlib.closing()`.
        """
        yield self.redis.close_manager()
        yield self.manager.close_manager()

    @staticmethod
    def _parse_config(config):
        riak_config = config.get('riak_manager', {})
        redis_config = config.get('redis_manager', {})
        return riak_config, redis_config

    @classmethod
    def from_config_sync(cls, config, amqp_client=None):
        riak_config, redis_config = cls._parse_config(config)
        manager = RiakManager.from_config(riak_config)
        redis = RedisManager.from_config(redis_config)
        sender = SyncMessageSender(amqp_client)
        metric_publisher = None
        if amqp_client is not None:
            metric_publisher = amqp_client.get_metric_publisher()
        return cls(manager, redis, sender, metric_publisher)

    @classmethod
    @inlineCallbacks
    def from_config_async(cls, config, command_publisher=None,
                          metric_publisher=None):
        # Note: This takes a publisher rather than a client to avoid leaking
        #       AMQP channels by making our own transient publishers.
        riak_config, redis_config = cls._parse_config(config)
        manager = TxRiakManager.from_config(riak_config)
        redis = yield TxRedisManager.from_config(redis_config)
        sender = AsyncMessageSender(command_publisher)
        returnValue(cls(manager, redis, sender, metric_publisher))

    @Manager.calls_manager
    def user_exists(self, user_account_key):
        """
        Check whether or not a user exists. Useful to check before creating
        a VumiUserApi since that does not do any type of checking itself.

        :param str user_account_key:
            The user account key to check.
        """
        user_data = yield self.get_user_account(user_account_key)
        returnValue(user_data is not None)

    def get_user_account(self, user_account_key):
        return self.account_store.get_user(user_account_key)

    def get_user_api(self, user_account_key, cleanup_api=False):
        return VumiUserApi(self, user_account_key, cleanup_api=cleanup_api)

    def send_command(self, worker_name, command, *args, **kwargs):
        """Create a VumiApiCommand and send it.

        :param str worker_name: Name of worker to send command to.
        :param str command: Type of command to send.
        :param *args: Positional args for command.
        :param **kwargs: Keyword args for command.
        """
        return self.mapi.send_command(
            VumiApiCommand.command(worker_name, command, *args, **kwargs))

    def get_metric_manager(self, prefix):
        if self.metric_publisher is None:
            raise VumiError("No metric publisher available.")
        return MetricManager(prefix, publisher=self.metric_publisher)

    @Manager.calls_manager
    def tagpool_set(self, pools):
        pool_data = dict([
            (pool, (yield self.tpm.get_metadata(pool)))
            for pool in pools])
        returnValue(TagpoolSet(pool_data))

    @Manager.calls_manager
    def known_tagpools(self):
        pools = yield self.tpm.list_pools()
        returnValue((yield self.tagpool_set(pools)))


class SyncMessageSender(object):
    def __init__(self, amqp_client):
        self.amqp_client = amqp_client

    def send_command(self, command):
        if self.amqp_client is None:
            raise VumiError("No command message publisher available.")
        if not self.amqp_client.is_connected():
            self.amqp_client.connect()
        self.amqp_client.publish_command_message(command)


class AsyncMessageSender(object):
    def __init__(self, command_publisher):
        self.command_publisher = command_publisher

    def send_command(self, command):
        if self.command_publisher is None:
            raise VumiError("No command message publisher available.")
        return self.command_publisher.publish_message(command)


class ApiCommandPublisher(Publisher):
    """
    Publisher for VumiApiCommand messages.
    """
    routing_key = "vumi.api"
    durable = True


class ApiEventPublisher(Publisher):
    """
    Publisher for VumiApiEvent messages.
    """
    routing_key = "vumi.event"
    durable = True


class VumiApiCommand(Message):
    @staticmethod
    def generate_id():
        """
        Generate a unique command id.

        There are places where we want an identifier before we can build a
        complete command. This lets us do that in a consistent manner.
        """
        return uuid4().get_hex()

    def process_fields(self, fields):
        fields.setdefault('command_id', self.generate_id())
        return fields

    @classmethod
    def command(cls, worker_name, command_name, *args, **kwargs):
        params = {
            'worker_name': worker_name,
            'command': command_name,
            'args': list(args),  # turn to list to make sure input & output
                                 # stay the same when encoded & decoded as
                                 # JSON.
            'kwargs': kwargs,
        }
        if "command_id" in kwargs:
            params["command_id"] = kwargs.pop("command_id")
        return cls(**params)

    @classmethod
    def conversation_command(cls, worker_name, command_name, user_account_key,
                             conversation_key, *args, **kwargs):
        kwargs.update({
            'user_account_key': user_account_key,
            'conversation_key': conversation_key,
        })
        return cls.command(worker_name, command_name, *args, **kwargs)


class VumiApiEvent(Message):
    @classmethod
    def event(cls, account_key, conversation_key, event_type, content):
        return cls(account_key=account_key,
                   conversation_key=conversation_key,
                   event_type=event_type,
                   content=content)
