# -*- test-case-name: go.vumitools.conversation.tests.test_utils -*-
# -*- coding: utf-8 -*-

from datetime import datetime
from collections import defaultdict

from twisted.internet.defer import returnValue

from vumi.persist.model import Manager

from go.vumitools.opt_out import OptOutStore
from go.vumitools.utils import MessageMetadataHelper
from go.vumitools.account import RoutingTableHelper, GoConnector


class ConversationWrapper(object):
    """Wrapper around a conversation, providing extended functionality.
    """

    def __init__(self, conversation, user_api):
        self.c = conversation
        self.user_api = user_api
        self.api = user_api.api
        self.mdb = self.api.mdb
        self.manager = self.c.manager
        self.base_manager = self.api.manager
        self._channels = None

    @Manager.calls_manager
    def stop_conversation(self):
        self.c.set_status_stopping()
        yield self.c.save()
        yield self.dispatch_command('stop',
                                    user_account_key=self.c.user_account.key,
                                    conversation_key=self.c.key)

    @Manager.calls_manager
    def archive_conversation(self):
        self.c.set_status_finished()
        yield self.c.save()
        yield self._remove_from_routing_table()
        yield self._release_batches()

    @Manager.calls_manager
    def _release_batches(self):
        for batch in (yield self.get_batches()):
            yield self.mdb.batch_done(batch.key)

    def __getattr__(self, name):
        # Proxy anything we don't have back to the wrapped conversation.
        return getattr(self.c, name)

    # TODO: Something about setattr?

    def get_config(self):
        return self.c.config

    def set_config(self, config):
        self.c.config = config

    def start_batch(self, *tags):
        user_account = unicode(self.c.user_account.key)
        return self.mdb.batch_start(tags, user_account=user_account)

    @Manager.calls_manager
    def get_batches(self):
        # NOTE: This assumes that we don't have very large numbers of batches.
        batches = []
        for bunch in self.c.batches.load_all_bunches(self.base_manager):
            batches.extend((yield bunch))
        returnValue(batches)

    def get_batch_keys(self):
        return self.c.batches.keys()

    @Manager.calls_manager
    def get_tags(self):
        """
        Return any tags associated with this conversation.

        :rtype:
            Returns a list of tags `[(tagpool, tag), ... ]`
        """
        tags = []
        for batch in (yield self.get_batches()):
            tags.extend((yield batch.tags))
        returnValue(tags)

    @Manager.calls_manager
    def get_channels(self):
        """
        Returns lists of channels that can either send messages to or receive
        messages from this conversation.

        NOTE: This channel list is cached and it is assumed that the reachable
              channels will not change over the lifetime of this object.

        :rtype:
            List of channel models.
        """
        if self._channels is not None:
            returnValue(self._channels)
        user_account = yield self.c.user_account.get(self.api.manager)
        routing_table = yield self.user_api.get_routing_table(user_account)
        rt_helper = RoutingTableHelper(routing_table)
        conn = GoConnector.for_conversation(
            self.conversation_type, self.key)
        incoming = rt_helper.transitive_sources(str(conn))
        outbound = rt_helper.transitive_targets(str(conn))
        connectors = incoming | outbound
        go_connectors = [GoConnector.parse(s) for s in connectors]
        channels = []
        for conn in go_connectors:
            if conn.ctype != conn.TRANSPORT_TAG:
                continue
            channel = yield self.user_api.get_channel(
                (conn.tagpool, conn.tagname))
            channels.append(channel)
        channels.sort(key=lambda c: c.name)
        self._channels = channels
        returnValue(channels)

    @Manager.calls_manager
    def has_channel_supporting(self, **kw):
        channels = yield self.get_channels()
        returnValue(any(channel.supports(**kw) for channel in channels))

    def has_channel_supporting_generic_sends(self):
        return self.has_channel_supporting(generic_sends=True)

    @Manager.calls_manager
    def get_progress_status(self):
        """
        Get an overview of the progress of this conversation

        :rtype: dict
            *sent* The number of messages sent.
            *ack* The number of messages that have been acknowledged
                    by the network for delivery
            *nack* The number of messages that have been seen by the network
                    but were actively refused for delivery.
            *delivery_report* The number of messages we've received
                    a delivery report for.
            *delivery_report_delivered* The number of delivery reports
                    indicating successful delivery.
            *delivery_report_failed* The number of delivery reports
                    indicating failed delivery.
            *delivery_report_pending* The number of delivery reports
                    indicating ongoing attempts to deliver the message.
        """
        statuses = dict((k, 0) for k in
                        ('sent', 'ack', 'nack', 'delivery_report',
                         'delivery_report_delivered', 'delivery_report_failed',
                         'delivery_report_pending'))

        for batch_id in self.get_batch_keys():
            batch_status = yield self.mdb.batch_status(batch_id)
            for k, v in batch_status.items():
                k = k.replace('.', '_')
                statuses[k] += v

        returnValue(statuses)

    @Manager.calls_manager
    def get_progress_percentage(self):
        """
        Get a percentage indication of how far along the sending
        of messages in this conversation is.

        :rtype: int
        """
        status = yield self.get_progress_status()
        if status['sent'] == 0:
            returnValue(0)
        sent_to_network = status['ack'] + status['nack']
        returnValue(int(sent_to_network / float(status['sent']) * 100))

    @Manager.calls_manager
    def get_groups(self):
        """
        Convenience method for loading all groups linked to this conversation.
        """
        groups = []
        for bunch in self.groups.load_all_bunches():
            groups.extend((yield bunch))
        returnValue(groups)

    def set_go_helper_metadata(self, helper_metadata=None):
        if helper_metadata is None:
            helper_metadata = {}
        go_metadata = helper_metadata.setdefault('go', {})
        go_metadata['user_account'] = self.user_account.key
        go_metadata['conversation_type'] = self.conversation_type
        go_metadata['conversation_key'] = self.key
        return helper_metadata

    @Manager.calls_manager
    def start(self):
        """Send the start command to this conversation's application worker.
        """
        batches = yield self.get_batches()
        if not batches:
            batch_id = yield self.start_batch()
            self.c.batches.add_key(batch_id)

        self.c.set_status_starting()
        yield self.c.save()

        yield self.dispatch_command('start',
                                    user_account_key=self.c.user_account.key,
                                    conversation_key=self.c.key)

    @Manager.calls_manager
    def _remove_from_routing_table(self):
        """Remove routing entries for this conversation.

        This only happens during archiving.
        """
        user_account = yield self.c.user_account.get(self.api.manager)
        routing_table = yield self.user_api.get_routing_table(user_account)
        rt_helper = RoutingTableHelper(routing_table)
        rt_helper.remove_conversation(self.c)
        yield user_account.save()

    @Manager.calls_manager
    def send_token_url(self, token_url, msisdn):
        """Send a confirmation/token link.
        """
        batch_id = yield self.get_latest_batch_key()

        # specify this message as being sensitive
        msg_options = {'helper_metadata': {'go': {'sensitive': True}}}

        yield self.dispatch_command(
            'send_message',
            user_account_key=self.c.user_account.key,
            conversation_key=self.c.key,
            command_data={
                "batch_id": batch_id,
                "to_addr": msisdn,
                "msg_options": msg_options,
                "content": ("Please visit %s to start your conversation." %
                            (token_url,)),
                })
        if batch_id not in self.c.batches.keys():
            self.c.batches.add_key(batch_id)
        yield self.c.save()

    @Manager.calls_manager
    def get_latest_batch_key(self):
        """
        Here be dragons.

        FIXME:  The existince of `get_latest_batch_key()` is a symptom of other
                things being wrong. We need to revisit how batches are stored
                on a conversation and whether we even need multiple batches
                per conversation.

                We're not storing timestamps on our batches and so we have no
                accurate way of telling which batch was most recenty acquired
                for this conversation. On top of this, our existing migration
                tools aren't mature enough to be able to describe the migration
                needed.

                Our current work around is looking at the cache to find out
                which batch_key had the last outbound message sent and return
                that batch_key
        """
        batch_keys = self.get_batch_keys()

        if not batch_keys:
            returnValue(None)

        # If there's only one then it's easy.
        if len(batch_keys) == 1:
            returnValue(batch_keys[0])

        # Cache this for however long this conversation object lives
        if hasattr(self, '_latest_batch_key'):
            returnValue(self._latest_batch_key)

        # Loop over the batch_keys and find out which one was most recently
        # used to send out a message.
        batch_key_timestamps = []
        for batch_key in batch_keys:
            if (yield self.mdb.cache.count_outbound_message_keys(batch_key)):
                [(_, timestamp)] = (yield self.mdb.get_outbound_message_keys(
                                        batch_key, 0, 0, with_timestamp=True))
                batch_key_timestamps.append((batch_key, timestamp))

        # We might not have anything to work with here since we might only have
        # batch_keys that haven't seen any outbound traffic
        if batch_key_timestamps:
            sorted_keys = sorted(batch_key_timestamps,
                                    key=lambda (key, ts): ts, reverse=True)
            latest = sorted_keys[0]
            self._latest_batch_key = latest[0]  # return only the key
            returnValue(self._latest_batch_key)

        # If there hasn't been any outbound traffic then just return the first
        # that Riak returned and hope for the best.
        self._latest_batch_key = batch_keys[0]
        returnValue(self._latest_batch_key)

    @Manager.calls_manager
    def count_replies(self, batch_key=None):
        """
        Count the total number of replies received.
        This is pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        count = yield self.mdb.cache.count_inbound_message_keys(batch_key)
        returnValue(count)

    @Manager.calls_manager
    def count_sent_messages(self, batch_key=None):
        """
        Count the total number of messages sent.
        This is pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        count = yield self.mdb.cache.count_outbound_message_keys(batch_key)
        returnValue(count)

    @Manager.calls_manager
    def count_inbound_uniques(self, batch_key=None):
        """
        Count the total unique `from_addr` values seen for the batch_key.
        Pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        count = yield self.mdb.cache.count_from_addrs(batch_key)
        returnValue(count)

    @Manager.calls_manager
    def count_outbound_uniques(self, batch_key=None):
        """
        Count the total unique `to_addr` values seen for the batch_key.
        Pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        count = yield self.mdb.cache.count_to_addrs(batch_key)
        returnValue(count)

    @Manager.calls_manager
    def collect_messages(self, keys, proxy, include_sensitive, scrubber):
        """
        Collect the messages using the given keys by using the given callback.

        :param list keys:
            The list of keys to retrieve.
        :param callable callback:
            The callback to use to load the object, this is given the key.
        :param bool include_sensitive:
            Whether or not to include hidden messages.
        :param callable scrubber:
            The scrubber to use on hidden messages. Should return a message
            object or None.
        """
        messages = []
        bunches = yield proxy.load_all_bunches(keys)
        for bunch in bunches:
            messages.extend((yield bunch))

        collection = []
        for message in messages:
            # vumi message is an attribute on the inbound message object
            msg = message.msg
            msg_mdh = MessageMetadataHelper(self.api, msg)
            if not msg_mdh.is_sensitive():
                collection.append(msg)
            elif include_sensitive:
                scrubbed_msg = scrubber(msg)
                if scrubbed_msg:
                    collection.append(scrubbed_msg)
        returnValue(collection)

    @Manager.calls_manager
    def received_messages(self, start=0, limit=100, batch_key=None,
                            include_sensitive=False, scrubber=None):
        """
        Get a list of replies from the message store. The keys come from
        the message store's cache.

        :param int start:
            Where to start in the result set.
        :param int limit:
            How many replies to get.
        :param str batch_key:
            The batch to get replies for. Defaults to whatever
            `get_latest_batch_key()` returns.
        :param bool include_sensitive:
            Whether or not to include hidden messages. Defaults to False.
            Hidden messages are messages with potentially sensitive information
            from a security point of view that should not be displayed in the
            UI by default.
        :param callable scrubber:
            If `include_sensitive` is True then the scrubber is called with the
            content of the message to be scrubbed. By default it is a noop
            which leaves the content unchanged.
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        if batch_key is None:
            returnValue([])
        scrubber = scrubber or (lambda msg: msg)

        # Redis counts from zero, so we - 1 on the limit.
        keys = yield self.mdb.cache.get_inbound_message_keys(batch_key, start,
                                                                limit - 1)

        replies = yield self.collect_messages(keys,
            self.mdb.inbound_messages, include_sensitive, scrubber)

        returnValue(replies)

    @Manager.calls_manager
    def sent_messages(self, start=0, limit=100, batch_key=None,
                        include_sensitive=False, scrubber=None):
        """
        Get a list of sent_messages from the message store. The keys come from
        the message store's cache.

        :param int start:
            Where to start
        :param int limit:
            How many sent messages to fetch starting from start
        :param str batch_key:
            The batch to get sent messages for. Defaults to whatever
            `get_latest_batch_key()` returns.
        :param bool include_sensitive:
            Whether or not to include hidden messages. Defaults to False.
            Hidden messages are messages with potentially sensitive information
            from a security point of view that should not be displayed in the
            UI by default.
        :param callable scrubber:
            If `include_sensitive` is True then the scrubber is called with the
            content of the message to be scrubbed. By default it is a noop
            which leaves the content unchanged.
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        if batch_key is None:
            returnValue([])
        scrubber = scrubber or (lambda msg: msg)

        keys = yield self.mdb.cache.get_outbound_message_keys(batch_key, start,
                                                                limit - 1)

        sent_messages = yield self.collect_messages(keys,
            self.mdb.outbound_messages, include_sensitive, scrubber)

        returnValue(sent_messages)

    @Manager.calls_manager
    def find_inbound_messages_matching(self, pattern, flags="i",
                                        batch_key=None, key="msg.content",
                                        ttl=None, wait=False):
        """
        Does a regex OR search over the inbound messages and returns
        matching messages.

        :param str pattern:
            The pattern to search on
        :param str flags:
            The flags to set for the RegExp object.
        :param str batch_key:
            The batch to search over.
        :param str key:
            The key on the message to match. Defaults to `msg.content`.
        :param int start:
            Where to start fetching results from.
        :param int limit:
            How many results to get.
        :param int ttl:
            How long to cache the results for.
            Defaults to the MessageStore default.
        :param bool wait:
            Wait with returning keys until the results are actually available.

        NOTE:   This should only be called from inside twisted as
                MessageStore.find_inbound_keys_matching() relies
                on Deferreds being fired.
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        query = [{
            "key": key,
            "pattern": pattern,
            "flags": flags,
            }]
        resp = yield self.mdb.find_inbound_keys_matching(batch_key, query,
                                                            ttl=ttl, wait=wait)
        returnValue(resp)

    @Manager.calls_manager
    def get_inbound_messages_for_token(self, token, start=0, stop=-1,
                                        batch_key=None):
        """
        Fetch the results for a search token
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        keys = yield self.mdb.get_keys_for_token(batch_key, token, start, stop)
        messages = []
        for bunch in self.mdb.inbound_messages.load_all_bunches(keys):
            messages.extend((yield bunch))
        returnValue(messages)

    @Manager.calls_manager
    def count_inbound_messages_for_token(self, token, batch_key=None):
        """
        Return the total number of keys in the results for the token.
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        count = yield self.mdb.count_keys_for_token(batch_key, token)
        returnValue(count)

    @Manager.calls_manager
    def find_outbound_messages_matching(self, pattern, flags="i",
                                        batch_key=None, key="msg.content",
                                        ttl=None, wait=False):
        """
        Does a regex OR search over the outbound messages and returns
        matching messages.

        :param str pattern:
            The pattern to search on
        :param str flags:
            The flags to set for the RegExp object.
        :param str batch_key:
            The batch to search over.
        :param str key:
            The key on the message to match. Defaults to `msg.content`.
        :param int ttl:
            How long to store the results for in seconds.
            Defaults to the MessageStore default.
        :param bool wait:
            Wait with returning keys until the results are actually available.
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        query = [{
            "key": key,
            "pattern": pattern,
            "flags": flags,
            }]
        resp = yield self.mdb.find_outbound_keys_matching(batch_key, query,
                                                            ttl=ttl, wait=wait)
        returnValue(resp)

    @Manager.calls_manager
    def get_outbound_messages_for_token(self, token, start=0, stop=-1,
                                        batch_key=None):
        """
        Fetch the results for a search token
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        keys = yield self.mdb.get_keys_for_token(batch_key, token, start, stop)
        messages = []
        for bunch in self.mdb.outbound_messages.load_all_bunches(keys):
            messages.extend((yield bunch))
        returnValue(messages)

    @Manager.calls_manager
    def get_aggregate_count(self, direction, batch_key=None, bucket_func=None):
        aggregate_keys = yield self.get_aggregate_keys(direction,
                                                        batch_key, bucket_func)
        returnValue([(bucket, len(keys)) for bucket, keys in aggregate_keys])

    @Manager.calls_manager
    def get_aggregate_keys(self, direction, batch_key=None, bucket_func=None):
        """
        Get aggregated total count of messages handled bucketed per day.
        :param str batch_key:
            The batch to get aggregates for. Defaults to whatever
            `get_latest_batch_key()` returns.
        :param callable bucket_func:
            A function that when given a timestamp returns an appropriate
            value that will be used as the bucket key.
        """
        message_callback = {
            'inbound': self.mdb.get_inbound_message_keys,
            'outbound': self.mdb.get_outbound_message_keys,
        }.get(direction, self.mdb.get_inbound_message_keys)

        batch_key = batch_key or (yield self.get_latest_batch_key())
        bucket_func = bucket_func or (lambda dt: dt.date())
        results = yield message_callback(batch_key, with_timestamp=True)
        aggregates = defaultdict(list)
        for key, timestamp in results:
            bucket = bucket_func(datetime.fromtimestamp(timestamp))
            aggregates[bucket].append(key)

        returnValue(sorted(aggregates.items()))

    def dispatch_command(self, command, *args, **kwargs):
        """
        Send a command to the GoApplication worker listening to this
        conversation type's worker name. The *args and **kwargs
        are expanded when the command is called.

        :type command: str
        :params command:
            The name of the command to call
        """
        worker_name = '%s_application' % (self.conversation_type,)
        return self.api.send_command(worker_name, command, *args, **kwargs)

    def get_absolute_url(self):
        return u'/app/%s/%s/' % (self.conversation_type, self.key)

    def get_contact_keys(self):
        """
        Get all contact keys for this conversation.
        """
        contact_store = self.user_api.contact_store
        return contact_store.get_contacts_for_conversation(self.c)

    @Manager.calls_manager
    def get_inbound_throughput(self, batch_key=None, sample_time=300):
        """
        Calculate how many inbound messages per minute we've been
        doing on average.
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        count = yield self.mdb.cache.count_inbound_throughput(batch_key,
            sample_time)
        returnValue(count / (sample_time / 60.0))

    @Manager.calls_manager
    def get_outbound_throughput(self, batch_key=None, sample_time=300):
        """
        Calculate how many outbound messages per minute we've been
        doing on average.
        """
        batch_key = batch_key or (yield self.get_latest_batch_key())
        count = yield self.mdb.cache.count_outbound_throughput(batch_key,
            sample_time)
        returnValue(count / (sample_time / 60.0))

    @Manager.calls_manager
    def _filter_opted_out_contacts(self, contacts, delivery_class):
        # TODO: Less hacky address type handling.
        address_type = 'gtalk' if delivery_class == 'gtalk' else 'msisdn'
        contacts = yield contacts
        opt_out_store = OptOutStore(
            self.api.manager, self.user_api.user_account_key)

        addresses = self.get_contacts_addresses(contacts)
        opt_out_keys = yield opt_out_store.opt_outs_for_addresses(
            address_type, addresses)
        opted_out_addrs = set(key.split(':')[1] for key in opt_out_keys)

        filtered_contacts = []
        for contact in contacts:
            contact_addr = contact.addr_for(delivery_class)
            if contact_addr and contact_addr not in opted_out_addrs:
                filtered_contacts.append(contact)
        returnValue(filtered_contacts)

    @Manager.calls_manager
    def get_opted_in_contact_bunches(self, delivery_class):
        """
        Get a generator that produces batches the contacts with
        an address attribute that is appropriate for the conversation's
        delivery_class and that are opted in.
        """
        contact_store = self.user_api.contact_store
        contact_keys = yield self.get_contact_keys()
        contacts_iter = yield contact_store.contacts.load_all_bunches(
            contact_keys)

        # We return a generator here. It's important that this is iterated over
        # slowly, otherwise we risk hammering our Riak servers to death.
        def opted_in_contacts_generator():
            # NOTE: This is a generator, *not* an async flattener.
            for contacts_bunch in contacts_iter:
                yield self._filter_opted_out_contacts(
                    contacts_bunch, delivery_class)

        returnValue(opted_in_contacts_generator())
