"""Utilities for Go API."""

from txjsonrpc.jsonrpc import BaseSubhandler
from txjsonrpc.jsonrpclib import Fault


class GoApiError(Fault):
    """Raise this to report an error from within an action handler."""

    def __init__(self, msg, fault_code=400):
        super(GoApiError, self).__init__(fault_code, msg)


class GoApiSubHandler(BaseSubhandler, object):
    """Base class for Go API JSON-RPC sub-handlers."""

    def __init__(self, user_account_key, vumi_api):
        super(GoApiSubHandler, self).__init__()
        # We could get either bytes or unicode here. Decode if necessary.
        if not isinstance(user_account_key, unicode):
            user_account_key = user_account_key.decode('utf8')
        self.user_account_key = user_account_key
        self.vumi_api = vumi_api

    def get_user_api(self, campaign_key):
        """Return a user_api for a particular campaign."""
        if campaign_key != self.user_account_key:
            raise GoApiError("Unknown campaign key.", fault_code=404)
        return self.vumi_api.get_user_api(campaign_key)
