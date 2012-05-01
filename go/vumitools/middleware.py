# -*- test-case-name: go.vumitools.tests.test_middleware -*-
import sys

from twisted.internet.defer import inlineCallbacks

from vumi.middleware import TransportMiddleware, TaggingMiddleware
from vumi.application import TagpoolManager
from vumi.persist.txriak_manager import TxRiakManager
from vumi.utils import normalize_msisdn

from go.vumitools.api import get_redis
from go.vumitools.account import AccountStore


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


class DebitAccountMiddleware(TransportMiddleware):

    def setup_middleware(self):
        # TODO: There really needs to be a helper function to
        #       turn this config into a manager.
        mdb_config = self.config.get('message_store', {})
        mdb_prefix = mdb_config.get('store_prefix', 'message_store')
        manager = TxRiakManager.from_config({'bucket_prefix': mdb_prefix})
        self.accounts_store = AccountStore(manager)
        r_server = get_redis(self.config)
        tpm_config = self.config.get('tagpool_manager', {})
        tpm_prefix = tpm_config.get('tagpool_prefix', 'tagpool_store')
        self.tpm = TagpoolManager(r_server, tpm_prefix)

    @inlineCallbacks
    def _debit_account(self, user_account_key, pool):
        user = yield self.accounts_store.get_user(user_account_key)
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

    @staticmethod
    def map_msg_to_user(msg):
        """Convenience method for retrieving a user that was added
        to a message.
        """
        user_account = msg['helper_metadata'].get('go', {}).get('user_account')
        return user_account

    @staticmethod
    def add_user_to_message(msg, user_account_key):
        """Convenience method for adding a user to a message."""
        go_metadata = msg['helper_metadata'].setdefault('go', {})
        go_metadata['user_account'] = user_account_key

    @staticmethod
    def add_user_to_payload(payload, user_account_key):
        """Convenience method for adding a user to a message."""
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
        self._debit_account(user_account_key, tag[0])
        return msg
