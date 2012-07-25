# -*- test-case-name: go.vumitools.tests.test_middleware -*-
import sys

from vumi.middleware import (
    TransportMiddleware, TaggingMiddleware, BaseMiddleware)
from vumi.utils import normalize_msisdn
from vumi.components.tagpool import TagpoolManager

from go.vumitools.credit import CreditManager


class NormalizeMsisdnMiddleware(TransportMiddleware):

    def setup_middleware(self):
        self.country_code = self.config['country_code']
        self.strip_plus = self.config.get('strip_plus', False)

    def handle_inbound(self, message, endpoint):
        from_addr = normalize_msisdn(message.get('from_addr'),
                        country_code=self.country_code)
        message['from_addr'] = from_addr
        return message

    def handle_outbound(self, message, endpoint):
        if self.strip_plus:
            message['to_addr'] = message['to_addr'].lstrip('+')
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
        keyword = (message['content'] or '').strip()
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
        return message['helper_metadata'].get('optout', {}).get('optout')


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
