# -*- test-case-name: go.vumitools.tests.test_middleware -*-
from vumi.middleware import TransportMiddleware, TaggingMiddleware
from vumi.utils import normalize_msisdn

from go.vumitools.api import VumiApi

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


class DebitAccountMiddleware(TransportMiddleware):

    def setup_middleware(self):
        pass

    def _debit_account(self, user_account_key, pool):
        # TODO: implement
        pass

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

    def handle_outbound(self, msg, endpoint):
        # TODO: what actually happens when we raise an exception from
        #       inside middleware?
        # TODO: add the user_account to the message somewhere
        user_account_key = self.map_msg_to_user(msg)
        if user_account_key is None:
            raise NoUserError(msg)
        tag = TaggingMiddleware.map_msg_to_tag(msg)
        if tag is None:
            raise NoTagError(msg)
        self._debit_account(user_account_key, tag[0])
        return msg
