# -*- test-case-name: go.vumitools.conversation.tests.test_utils -*-
# -*- coding: utf-8 -*-

from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Manager

from vumi.middleware.tagger import TaggingMiddleware

from go.vumitools.exceptions import ConversationSendError
from go.vumitools.middleware import DebitAccountMiddleware
from go.vumitools.opt_out import OptOutStore


class ConversationWrapper(object):
    """Wrapper around a conversation, providing extended functionality.
    """

    def __init__(self, conversation, user_api):
        self.c = conversation
        self.user_api = user_api
        self.api = user_api.api
        self.mdb = self.api.mdb
        self.tpm = self.api.tpm
        self.manager = self.c.manager
        self.base_manager = self.api.manager
        self._tagpool_metadata = None

    @Manager.calls_manager
    def get_tagpool_metadata(self, key, default=None):
        if self._tagpool_metadata is None:
            self._tagpool_metadata = yield self.api.tpm.get_metadata(
                self.delivery_tag_pool)
        returnValue(self._tagpool_metadata.get(key, default))

    @Manager.calls_manager
    def end_conversation(self):
        self.c.end_timestamp = datetime.utcnow()
        yield self.c.save()
        yield self._release_batches()

    @Manager.calls_manager
    def _release_batches(self):
        for batch in (yield self.get_batches()):
            yield self.mdb.batch_done(batch.key)  # TODO: why key?
            for tag in batch.tags:
                yield self.tpm.release_tag(tag)

    def __getattr__(self, name):
        # Proxy anything we don't have back to the wrapped conversation.
        return getattr(self.c, name)

    # TODO: Something about setattr?

    def get_metadata(self, default=None):
        return self.c.metadata or default

    def set_metadata(self, metadata):
        self.c.metadata = metadata

    def start_batch(self, *tags):
        user_account = unicode(self.c.user_account.key)
        return self.mdb.batch_start(tags, user_account=user_account)

    def get_batches(self):
        return self.c.batches.get_all(self.base_manager)

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
            for k, v in self.mdb.batch_status(batch_id).items():
                k = k.replace('.', '_')
                statuses[k] += v

        return statuses

    def get_progress_percentage(self):
        """
        Get a percentage indication of how far along the sending
        of messages in this conversation is.

        :rtype: int
        """
        status = self.get_progress_status()
        if status['sent'] == 0:
            return 0
        return int(status['ack'] / float(status['sent']) * 100)

    @Manager.calls_manager
    def make_message_options(self, tag):
        msg_options = {}
        # TODO: transport_type is probably irrelevant
        msg_options['transport_type'] = yield self.get_tagpool_metadata(
            'transport_type')
        # TODO: not sure whether to declare that tag names must always be
        #       valid from_addr values or whether to put in a mapping somewhere
        msg_options['from_addr'] = tag[1]
        msg_options.update(
            (yield self.get_tagpool_metadata('msg_options', {})))
        TaggingMiddleware.add_tag_to_payload(msg_options, tag)
        DebitAccountMiddleware.add_user_to_payload(msg_options,
                                                   self.c.user_account.key)
        returnValue(msg_options)

    @Manager.calls_manager
    def start(self, no_batch_tag=False, acquire_tag=True, **extra_params):
        """
        Send the start command to this conversations application worker.
        """
        # TODO: Move some of this stuff out to a place where it makes more
        #       sense to have it.
        if acquire_tag:
            tag = yield self.acquire_tag()
        else:
            tag = yield self.acquire_existing_tag()
        batch_tags = [] if no_batch_tag else [tag]
        batch_id = yield self.start_batch(*batch_tags)

        msg_options = yield self.make_message_options(tag)

        is_client_initiated = yield self.is_client_initiated()
        yield self.dispatch_command('start',
            batch_id=batch_id,
            conversation_type=self.c.conversation_type,
            conversation_key=self.c.key,
            msg_options=msg_options,
            is_client_initiated=is_client_initiated,
            **extra_params)
        self.c.batches.add_key(batch_id)
        yield self.c.save()

    def get_latest_batch_key(self):
        """
        We're not storing timestamps on our batches and so we have no
        way of telling which batch was the most recent for this conversation.

        FIXME:  add timestamps to batches or remove the need for only allowing
                access to the cache one batch_id at the time (possibly by
                using Redis' zunionstore to provide a temporary cached
                view on all keys for a set of batch_ids)
        """
        batch_keys = self.get_batch_keys()
        if batch_keys:
            return batch_keys[0]

    def count_replies(self, batch_key=None):
        """
        Count the total number of replies received.
        This is pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or self.get_latest_batch_key()
        return self.mdb.cache.count_inbound_message_keys(batch_key)

    def count_sent_messages(self, batch_key=None):
        """
        Count the total number of messages sent.
        This is pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or self.get_latest_batch_key()
        return self.mdb.cache.count_outbound_message_keys(batch_key)

    def count_inbound_uniques(self, batch_key=None):
        """
        Count the total unique `from_addr` values seen for the batch_key.
        Pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or self.get_latest_batch_key()
        return self.mdb.cache.count_from_addrs(batch_key)

    def count_outbound_uniques(self, batch_key=None):
        """
        Count the total unique `to_addr` values seen for the batch_key.
        Pulled from the cache.

        :param str batch_key:
            The batch to count, defaults to `get_latest_batch_key()`
        """
        batch_key = batch_key or self.get_latest_batch_key()
        return self.mdb.cache.count_to_addrs(batch_key)

    @Manager.calls_manager
    def replies(self, start=0, limit=100, batch_key=None):
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
        """
        batch_key = batch_key or self.get_latest_batch_key()
        if batch_key is None:
            returnValue([])

        # Redis counts from zero, so we - 1 on the limit.
        keys = yield self.mdb.cache.get_inbound_message_keys(batch_key, start,
                                                        start + limit - 1)

        replies = []
        for key in keys:
            message = yield self.mdb.inbound_messages.load(key)
            replies.append((
                yield self._handle_message(message.msg, 'from_addr')))

        returnValue(replies)

    @Manager.calls_manager
    def _handle_message(self, message, addr_attribute):
        """
        FIXME:  The conversation view expects a bunch of other stuff alongside
                a message. This is horribly complex and needs to be fixed.
        """
        contact = yield self.user_api.contact_store.contact_for_addr(
                            self.delivery_class, message[addr_attribute])
        returnValue({
            'type': self.delivery_class,
            'source': self.delivery_class_description(),
            'contact': contact,
            'time': message['timestamp'],
            'content': message['content'],
            })

    @Manager.calls_manager
    def sent_messages(self, start=0, limit=100, batch_key=None):
        """
        Get a list of sent_messages from the message store. The keys come from
        the message store's cache.

        :param int page:
            Which page to get
        :param int limit:
            How many sent messages to get per page
        :param str batch_key:
            The batch to get sent messages for. Defaults to whatever
            `get_latest_batch_key()` returns.
        """
        batch_key = batch_key or self.get_latest_batch_key()

        keys = yield self.mdb.cache.get_outbound_message_keys(batch_key, start,
                                                        limit)

        sent_messages = []
        for key in keys:
            message = yield (self.mdb.outbound_messages.load(key))
            sent_messages.append((
                yield self._handle_message(message.msg, 'to_addr')))

        returnValue(sent_messages)

    @Manager.calls_manager
    def acquire_existing_tag(self):
        # TODO: Remove this once we have proper routing stuff.
        tag = (self.c.delivery_tag_pool, self.c.delivery_tag)
        inuse_tags = yield self.api.tpm.inuse_tags(tag[0])
        if tag not in inuse_tags:
            raise ConversationSendError("Requested tag not pre-acquired.")
        returnValue(tag)

    @Manager.calls_manager
    def acquire_tag(self):
        # TODO: Remove this once we have proper routing stuff.
        if self.c.delivery_tag is None:
            tag = yield self.api.acquire_tag(self.c.delivery_tag_pool)
            if tag is None:
                raise ConversationSendError("No spare messaging tags.")
        else:
            tag = (self.c.delivery_tag_pool, self.c.delivery_tag)
            tag = yield self.api.acquire_specific_tag(tag)
            if tag is None:
                raise ConversationSendError("Requested tag not available.")
        returnValue(tag)

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

    def delivery_class_description(self):
        """
        FIXME: This actually returns the tagpool display name.
               The function itself is probably correct -- the
               name of the function is probably wrong.
        """
        return self.get_tagpool_metadata('display_name',
                                         self.delivery_tag_pool)

    def is_client_initiated(self):
        """
        Check whether this conversation can only be initiated by a client.

        :rtype: bool
        """
        return self.get_tagpool_metadata('client_initiated', False)

    def get_absolute_url(self):
        return u'/app/%s/%s/' % (self.conversation_type, self.key)

    @Manager.calls_manager
    def get_opted_in_contacts(self):
        """
        Get all the contacts that are both assigned to this group and opted in.
        """
        contact_store = self.user_api.contact_store
        contacts = yield contact_store.get_contacts_for_conversation(self.c)
        returnValue(contacts)

    @Manager.calls_manager
    def get_opted_in_addresses(self):
        """
        Get the contacts assigned to this group with an address attribute
        that is appropriate for the conversation's delivery_class and
        that are opted in.
        """
        # TODO: Unhacky this.
        opt_out_store = OptOutStore(
            self.api.manager, self.user_api.user_account_key)
        optouts = yield opt_out_store.list_opt_outs()
        optout_addrs = [optout.key.split(':', 1)[1] for optout in optouts
                            if optout.key.startswith('msisdn:')]
        contacts = yield self.get_opted_in_contacts()
        all_addrs = yield self.get_contacts_addresses(contacts)
        opted_in_addrs = [addr for addr in all_addrs
                            if addr not in optout_addrs]
        returnValue(opted_in_addrs)
