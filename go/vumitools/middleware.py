# -*- test-case-name: go.vumitools.tests.test_middleware -*-
import sys

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.middleware import (TransportMiddleware, TaggingMiddleware,
                                BaseMiddleware)
from vumi.application import TagpoolManager
from vumi.utils import normalize_msisdn
from vumi.persist.txriak_manager import TxRiakManager
from vumi.persist.message_store import MessageStore
from vumi import log

from go.vumitools.credit import CreditManager
from go.vumitools.account import AccountStore
from go.vumitools.conversation import ConversationStore


class NormalizeMsisdnMiddleware(TransportMiddleware):

    def setup_middleware(self):
        self.country_code = self.config['country_code']

    def handle_inbound(self, message, endpoint):
        from_addr = normalize_msisdn(message.get('from_addr'),
                        country_code=self.country_code)
        message['from_addr'] = from_addr
        return message


class DebitAccountError(Exception):
    """Exception raised if a message can't be paid for."""


class NoUserError(DebitAccountError):
    """Account could not be debited because no user was found."""


class NoTagError(DebitAccountError):
    """Account could not be debited because no tag was found."""


class BadTagPool(DebitAccountError):
    """Account could not be debited because the tag pool doesn't
       specify a cost."""


class InsufficientCredit(DebitAccountError):
    """Account could not be debited because the user account has
       insufficient credit."""


class GoApplicationRouterMiddleware(BaseMiddleware):
    """
    Base class for middlewares used by dispatchers using the
    `GoApplicationRouter`. It configures the `account_store` and the
    `message_store`.

    :type message_store: dict
    :param message_store:
        Dictionary containing the following values:

        *store_prefix*: the store prefix, defaults to 'message_store'

    :type redis: dict
    :param redis:
        Dictionary containing the configuration parameters for connecting
        to Redis with. Passed along as **kwargs to the Redis client.

    """
    def setup_middleware(self):
        from go.vumitools.api import get_redis
        r_server = get_redis(self.config)

        mdb_config = self.config.get('message_store', {})
        self.mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        r_server = get_redis(self.config)
        self.manager = TxRiakManager.from_config({
                'bucket_prefix': self.mdb_prefix})
        self.account_store = AccountStore(self.manager)
        self.message_store = MessageStore(self.manager, r_server,
                                            self.mdb_prefix)

    def add_metadata_to_message(self, message):
        """
        Subclasses should override this method to appropriately set values
        on a message's `helper_metadata`. If specific message types or
        directions require different behaviour they can be overridden
        separately.
        """
        raise NotImplementedError("add_metadata_to_message should be "
                                    "implemented by the subclass")

    @inlineCallbacks
    def handle_inbound(self, message, endpoint):
        yield self.add_metadata_to_message(message)
        returnValue(message)

    @inlineCallbacks
    def handle_event(self, event, endpoint):
        yield self.add_metadata_to_message(event)
        returnValue(event)

    @inlineCallbacks
    def handle_outbound(self, message, endpoint):
        yield self.add_metadata_to_message(message)
        returnValue(message)


class LookupAccountMiddleware(GoApplicationRouterMiddleware):
    """
    Look up the account_key for a given message by retrieving
    this from the message tag's info.

    *NOTE*  This requires the `TaggingMiddleware` to be configured and placed
            before this middleware for this to work as it expects certain
            values to be set in the `helper_metadata`
    """

    @inlineCallbacks
    def find_account_key_for_message(self, message):
        # NOTE: there is probably a better way of doing this when given a
        #       batch key but I'm not seeing it right now.
        tag = TaggingMiddleware.map_msg_to_tag(message)
        if tag:
            current_tag = yield self.message_store.get_tag_info(tag)
            if current_tag:
                batch = yield current_tag.current_batch.get()
                if batch:
                    returnValue(batch.metadata['user_account'])

    @inlineCallbacks
    def add_metadata_to_message(self, message):
        account_key = yield self.find_account_key_for_message(message)
        if account_key:
            helper_metadata = message.get('helper_metadata', {})
            go_metadata = helper_metadata.setdefault('go', {})
            go_metadata['user_account'] = account_key

    @staticmethod
    def map_message_to_account_key(message):
        go_metadata = message.get('helper_metadata', {}).setdefault('go', {})
        return go_metadata.get('user_account')


class LookupBatchMiddleware(GoApplicationRouterMiddleware):
    """
    Look up a `batch_key` by inspecting the tag for a given message.

    *NOTE*  This requires the `TaggingMiddleware` to be configured and placed
            before this middleware to ensure that the appropriate tagging
            values are set in the `helper_metadata`
    """

    @inlineCallbacks
    def find_batch_for_message(self, message):
        tag = TaggingMiddleware.map_msg_to_tag(message)
        if tag:
            current_tag = yield self.message_store.get_tag_info(tag)
            if current_tag:
                batch = yield current_tag.current_batch.get()
                returnValue(batch)

    @inlineCallbacks
    def add_metadata_to_message(self, message):
        batch = yield self.find_batch_for_message(message)
        if batch:
            helper_metadata = message.get('helper_metadata', {})
            go_metadata = helper_metadata.setdefault('go', {})
            go_metadata['batch_key'] = batch.key

    @staticmethod
    def map_message_to_batch_key(message):
        go_metadata = message.get('helper_metadata', {}).get('go', {})
        return go_metadata.get('batch_key')


class LookupConversationMiddleware(GoApplicationRouterMiddleware):
    """
    Look up a conversation based on the `account_key` and `batch_key` that
    have been stored in the `helper_metadata` by the `LookupAccountMiddleware`
    and the `LookupBatchMiddleware` middlewares.

    *NOTE*  This middleware depends on the `LookupAccountMiddleware`,
            `LookupBatchMiddleware` and the `TaggingMiddleware` being
            configured and placed before this middleware to ensure that the
            appropriate variables are set in the `helper_metadata`
    """

    @inlineCallbacks
    def find_conversation_for_message(self, message):
        account_key = LookupAccountMiddleware.map_message_to_account_key(
                                                                    message)
        batch_key = LookupBatchMiddleware.map_message_to_batch_key(message)
        if account_key and batch_key:
            conversation_store = ConversationStore(self.manager, account_key)
            account_submanager = conversation_store.manager
            batch = self.message_store.batches(batch_key)
            all_conversations = yield batch.backlinks.conversations(
                                                            account_submanager)
            conversations = [c for c in all_conversations if not
                                c.ended()]
            if conversations:
                if len(conversations) > 1:
                    conv_keys = [c.key for c in conversations]
                    log.warning('Multiple conversations found '
                        'going with most recent: %r' % (conv_keys,))
                conversation = sorted(conversations, reverse=True,
                    key=lambda c: c.start_timestamp)[0]
                returnValue(conversation)

    @inlineCallbacks
    def add_metadata_to_message(self, message):
        conversation = yield self.find_conversation_for_message(message)
        if conversation:
            helper_metadata = message.get('helper_metadata', {})
            conv_metadata = helper_metadata.setdefault('conversations', {})
            conv_metadata['conversation_key'] = conversation.key
            conv_metadata['conversation_type'] = conversation.conversation_type

    @staticmethod
    def map_message_to_conversation_info(message):
        helper_metadata = message.get('helper_metadata', {})
        conv_metadata = helper_metadata.get('conversations', {})
        if conv_metadata:
            return (
                conv_metadata['conversation_key'],
                conv_metadata['conversation_type']
            )


class OptOutMiddleware(BaseMiddleware):

    def setup_middleware(self):
        self.keyword_separator = self.config.get('keyword_separator', ' ')
        self.case_sensitive = self.config.get('case_sensitive', False)
        keywords = self.config.get('optout_keywords', [])
        self.optout_keywords = set([self.casing(word)
                                        for word in keywords])

    def casing(self, word):
        if not self.case_sensitive:
            return word.lower()
        return word

    def handle_inbound(self, message, endpoint):
        keyword = message['content'].strip()
        helper_metadata = message['helper_metadata']
        optout_metadata = helper_metadata.setdefault('optout', {})
        if self.casing(keyword) in self.optout_keywords:
            optout_metadata['optout'] = True
            optout_metadata['optout_keyword'] = self.casing(keyword)
        else:
            optout_metadata['optout'] = False
        return message

    @staticmethod
    def is_optout_message(message):
        return message['helper_metadata'].setdefault('optout').get('optout')


class DebitAccountMiddleware(TransportMiddleware):

    def setup_middleware(self):
        # TODO: There really needs to be a helper function to
        #       turn this config into managers.
        from go.vumitools.api import get_redis
        r_server = get_redis(self.config)
        tpm_config = self.config.get('tagpool_manager', {})
        tpm_prefix = tpm_config.get('tagpool_prefix', 'tagpool_store')
        self.tpm = TagpoolManager(r_server, tpm_prefix)
        cm_config = self.config.get('credit_manager', {})
        cm_prefix = cm_config.get('credit_prefix', 'credit_store')
        self.cm = CreditManager(r_server, cm_prefix)

    def _credits_per_message(self, pool):
        tagpool_metadata = self.tpm.get_metadata(pool)
        credits_per_message = tagpool_metadata.get('credits_per_message')
        try:
            credits_per_message = int(credits_per_message)
            assert credits_per_message >= 0
        except Exception:
            exc_tb = sys.exc_info()[2]
            raise (BadTagPool,
                   BadTagPool("Invalid credits_per_message for pool %r"
                              % (pool,)),
                   exc_tb)
        return credits_per_message

    @staticmethod
    def map_msg_to_user(msg):
        """Convenience method for retrieving a user that was added
        to a message.
        """
        user_account = msg['helper_metadata'].get('go', {}).get('user_account')
        return user_account

    @staticmethod
    def map_payload_to_user(payload):
        """Convenience method for retrieving a user from a payload."""
        go_metadata = payload.get('helper_metadata', {}).get('go', {})
        return go_metadata.get('user_account')

    @staticmethod
    def add_user_to_message(msg, user_account_key):
        """Convenience method for adding a user to a message."""
        go_metadata = msg['helper_metadata'].setdefault('go', {})
        go_metadata['user_account'] = user_account_key

    @staticmethod
    def add_user_to_payload(payload, user_account_key):
        """Convenience method for adding a user to a message payload."""
        helper_metadata = payload.setdefault('helper_metadata', {})
        go_metadata = helper_metadata.setdefault('go', {})
        go_metadata['user_account'] = user_account_key

    def handle_outbound(self, msg, endpoint):
        # TODO: what actually happens when we raise an exception from
        #       inside middleware?
        user_account_key = self.map_msg_to_user(msg)
        if user_account_key is None:
            raise NoUserError(msg)
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        if tag is None:
            raise NoTagError(msg)
        credits_per_message = self._credits_per_message(tag[0])
        self._debit_account(user_account_key, credits_per_message)
        success = self.cm.debit(user_account_key, credits_per_message)
        if not success:
            raise InsufficientCredit("User %r has insufficient credit"
                                     " to debit %r." %
                                     (user_account_key, credits_per_message))
        return msg
