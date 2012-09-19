# -*- test-case-name: go.vumitools.tests.test_api -*-
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
                        ('sent', 'ack', 'delivery_report',
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
    def start(self, no_batch_tag=False, acquire_tag=True, **extra_params):
        """
        Send the start command to this conversations application worker.
        """
        if acquire_tag:
            tag = yield self.acquire_tag()
        else:
            tag = yield self.acquire_existing_tag()
        batch_tags = [] if no_batch_tag else [tag]
        batch_id = yield self.start_batch(*batch_tags)

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

    @Manager.calls_manager
    def replies(self, limit=100):
        """
        FIXME: this requires a contact to already exist in the database
                before it can show up as a reply. Isn't going to work
                for things like USSD and in some cases SMS.
        """
        batch_keys = self.get_batch_keys()
        reply_statuses = []
        replies = []
        cache = {}
        for batch_id in batch_keys:
            # TODO: Not look up the batch by key again.
            replies.extend((yield self.mdb.batch_replies(batch_id)))
        for reply in replies[:limit]:
            cache_key = '/'.join([self.delivery_class, reply['from_addr']])
            contact = cache.get(cache_key, None)
            if not contact:
                contact = yield self.user_api.contact_store.contact_for_addr(
                    self.delivery_class, reply['from_addr'])
                cache[cache_key] = contact
            reply_statuses.append({
                'type': self.delivery_class,
                'source': self.delivery_class_description(),
                'contact': contact,
                'time': reply['timestamp'],
                'content': reply['content'],
                })
        returnValue(sorted(reply_statuses,
                           key=lambda reply: reply['time'],
                           reverse=True))

    @Manager.calls_manager
    def sent_messages(self, limit=100):
        batch_keys = self.get_batch_keys()
        outbound_statuses = []
        messages = []
        for batch_id in batch_keys:
            # TODO: Not look up the batch by key again.
            messages.extend((yield self.mdb.batch_messages(batch_id)))
        for message in messages[:limit]:
            contact = yield self.user_api.contact_store.contact_for_addr(
                    self.delivery_class, message['to_addr'])
            outbound_statuses.append({
                'type': self.delivery_class,
                'source': self.delivery_class_description(),
                'contact': contact,
                'time': message['timestamp'],
                'content': message['content']
                })
        returnValue(sorted(outbound_statuses, key=lambda sent: sent['time'],
                           reverse=True))

    @Manager.calls_manager
    def acquire_existing_tag(self):
        tag = (self.c.delivery_tag_pool, self.c.delivery_tag)
        inuse_tags = yield self.api.tpm.inuse_tags(tag[0])
        if tag not in inuse_tags:
            raise ConversationSendError("Requested tag not pre-acquired.")
        returnValue(tag)

    @Manager.calls_manager
    def acquire_tag(self):
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
