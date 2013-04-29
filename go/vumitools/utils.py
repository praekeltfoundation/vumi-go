# -*- test-case-name: go.vumitools.tests.test_utils -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.middleware.tagger import TaggingMiddleware


class MessageMetadataHelper(object):
    """Look up various bits of metadata for a Vumi Go message.

    Any Go inbound message that has reached the main dispatcher, will already
    have at least `user_account_key` in helper metadata. `conversation_type`
    and `conversation_key` are set once the message gets routed to the
    conversation.

    TODO: Something about non-conversation routing blocks.

    We store metadata in two places:

    1. Keys into the various stores go into the message helper_metadata.
       This is helpful for preventing unnecessary duplicate lookups between
       workers.

    2. Objects retreived from those stores get stashed on the message object.
       This is helpful for preventing duplicate lookups within a worker.
       (Between different middlewares, for example.)
    """

    def __init__(self, vumi_api, message):
        self.vumi_api = vumi_api
        self.message = message

        # Easier access to metadata.
        message_metadata = message.get('helper_metadata', {})
        self._go_metadata = message_metadata.setdefault('go', {})

        # A place to store objects we don't want serialised.
        if not hasattr(message, '_store_objects'):
            message._store_objects = {}
        self._store_objects = message._store_objects

        # If we don't have a tag, we want to blow up early in some places.
        self.tag = TaggingMiddleware.map_msg_to_tag(message)

    def is_sensitive(self):
        """
        Returns True if the contents of the message have been marked as
        being sensitive. This could mean the SMS contains information such as
        unique codes, airtime pins or other values that should not be displayed
        in a UI
        """
        return bool(self._go_metadata.get('sensitive'))

    def has_user_account(self):
        return 'user_account' in self._go_metadata

    def get_account_key(self):
        # TODO: Better exception.
        return self._go_metadata['user_account']

    def get_user_api(self):
        return self.vumi_api.get_user_api(self.get_account_key())

    def get_conversation_key(self):
        # TODO: Better exception.
        return self._go_metadata['conversation_key']

    def get_conversation(self):
        return self.get_user_api().get_wrapped_conversation(
            self.get_conversation_key())

    def get_conversation_info(self):
        conversation_info = {}

        for field in ['user_account', 'conversation_type', 'conversation_key']:
            if field in self._go_metadata:
                conversation_info[field] = self._go_metadata[field]

        if len(conversation_info) != 3:
            return None
        return conversation_info

    def set_conversation_info(self, conversation_type, conversation_key):
        self._go_metadata.update({
            'conversation_type': conversation_type,
            'conversation_key': conversation_key,
        })

    def set_user_account(self, user_account):
        self._go_metadata.update({
            'user_account': user_account,
        })


class OldGoMessageMetadata(object):
    """Look up various bits of metadata for a Vumi Go message.

    We store metadata in two places:

    1. Keys into the various stores go into the message helper_metadata.
       This is helpful for preventing unnecessary duplicate lookups between
       workers.

    2. Objects retreived from those stores get stashed on the message object.
       This is helpful for preventing duplicate lookups within a worker.
       (Between different middlewares, for example.)
    """

    def __init__(self, vumi_api, message):
        self.vumi_api = vumi_api
        self.message = message

        # Easier access to metadata.
        message_metadata = message.get('helper_metadata', {})
        self._go_metadata = message_metadata.setdefault('go', {})

        # A place to store objects we don't want serialised.
        if not hasattr(message, '_store_objects'):
            message._store_objects = {}
        self._store_objects = message._store_objects

        # If we don't have a tag, we want to blow up early in some places.
        self.tag = TaggingMiddleware.map_msg_to_tag(message)

    def is_sensitive(self):
        """
        Returns True if the contents of the message have been marked as
        being sensitive. This could mean the SMS contains information such as
        unique codes, airtime pins or other values that should not be displayed
        in a UI
        """
        return self._go_metadata.get('sensitive') == True

    @inlineCallbacks
    def _get_tag_info(self):
        if not self.tag:
            # Without a tag, there's no point in bothering.
            return

        if 'tag_info' in self._store_objects:
            # We already have this, no need to look it up.
            returnValue(self._store_objects['tag_info'])

        # Get it from the message store.
        tag_info = yield self.vumi_api.mdb.get_tag_info(self.tag)
        self._store_objects['tag_info'] = tag_info
        returnValue(tag_info)

    @inlineCallbacks
    def _find_batch(self):
        if 'batch' in self._store_objects:
            # We already have this, no need to look it up.
            returnValue(self._store_objects['batch'])

        if 'batch_key' in self._go_metadata:
            # We know what it is, we just need to get it.
            batch = yield self.vumi_api.mdb.get_batch(
                self._go_metadata['batch_key'])
            self._store_objects['batch'] = batch
            returnValue(batch)

        # Look it up from the tag, assuming we have one.
        tag_info = yield self._get_tag_info()
        if tag_info:
            batch = yield tag_info.current_batch.get()
            if batch is not None:
                self._store_objects['batch'] = batch
                self._go_metadata['batch_key'] = batch.key
                returnValue(batch)
            else:
                # TODO: change this back to .error() once close a
                #       conversation doesn't cause it to be triggered for
                #       every message.
                log.msg('Cannot find batch for tag_info %s' % (tag_info,))

    @inlineCallbacks
    def get_batch_key(self):
        if 'batch_key' not in self._go_metadata:
            # We're calling _find_batch() for the side effect, which is to put
            # the batch key in the metadata if there is one.
            yield self._find_batch()
        returnValue(self._go_metadata.get('batch_key'))

    @inlineCallbacks
    def _find_account_key(self):
        if 'user_account' in self._go_metadata:
            # We already have this, no need to look it up.
            returnValue(self._go_metadata['user_account'])

        # Look it up from the batch, assuming we can get one.
        batch = yield self._find_batch()
        if batch:
            user_account_key = batch.metadata['user_account']
            self._go_metadata['user_account'] = user_account_key
            returnValue(user_account_key)

    @inlineCallbacks
    def get_account_key(self):
        if 'user_account' not in self._go_metadata:
            # We're calling _find_account_key() for the side effect, which is
            # to put the account key in the metadata if there is one.
            yield self._find_account_key()
        returnValue(self._go_metadata.get('user_account'))

    @inlineCallbacks
    def _get_conversation_store(self):
        if 'conv_store' in self._store_objects:
            returnValue(self._store_objects['conv_store'])

        # We need an account key to get at a conversation.
        account_key = yield self.get_account_key()
        if not account_key:
            return

        user_api = self.vumi_api.get_user_api(account_key)
        conv_store = user_api.conversation_store
        self._store_objects['conv_store'] = conv_store
        returnValue(conv_store)

    @inlineCallbacks
    def get_conversation(self):
        if 'conversation' in self._store_objects:
            # We already have this, no need to look it up.
            returnValue(self._store_objects['conversation'])

        # We need a conversation store.
        conv_store = yield self._get_conversation_store()
        if not conv_store:
            return

        if 'conversation_key' in self._go_metadata:
            # We know what it is, we just need to get it.
            conversation = yield conv_store.get_conversation_by_key(
                self._go_metadata['conversation_key'])
            returnValue(conversation)

        batch = yield self._find_batch()
        if not batch:
            # Without a batch, we can't get a conversation.
            return

        conv_keys = yield batch.backlinks.conversations(conv_store.manager)
        conv_model = conv_store.conversations
        bunches = yield conv_model.load_all_bunches(conv_keys)
        conversations = []
        for bunch in bunches:
            conversations.extend((yield bunch))
        if not conversations:
            # No open conversations for this batch.
            return

        # We may have more than one conversation here.
        if len(conversations) > 1:
            log.warning('Multiple conversations found '
                        'going with most recent: %r' % (conv_keys,))
        conversation = sorted(conversations, reverse=True,
                              key=lambda c: c.start_timestamp)[0]

        self._go_metadata['conversation_key'] = conversation.key
        self._go_metadata['conversation_type'] = conversation.conversation_type
        returnValue(conversation)

    @inlineCallbacks
    def get_conversation_info(self):
        if 'conversation_key' not in self._go_metadata:
            conv = yield self.get_conversation()
            if conv is None:
                # We couldn't find a conversation.
                return
        returnValue((self._go_metadata['conversation_key'],
                     self._go_metadata['conversation_type']))

    def set_conversation_info(self, conversation):
        self._go_metadata['conversation_key'] = conversation.key
        self._go_metadata['conversation_type'] = conversation.conversation_type
