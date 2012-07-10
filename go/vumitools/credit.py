# -*- test-case-name: go.vumitools.tests.test_credit -*-

# TODO: create worker that updates Riak

from twisted.internet.defer import returnValue

from vumi.persist.redis_base import Manager


class CreditManager(object):
    def __init__(self, redis):
        self.redis = redis
        self.manager = redis  # TODO: hack to make calls_manager work

    @Manager.calls_manager
    def get_credit(self, user_account_key):
        """Return the amount of credit available.

        :returns:
           Number of credits available (or None if the user isn't in
           the credit store yet).
        """
        credit_key = self._credit_key(user_account_key)
        credit = yield self.redis.get(credit_key)
        if credit is not None:
            credit = int(credit)
        returnValue(credit)

    @Manager.calls_manager
    def credit(self, user_account_key, amount):
        """Add an amount of credits to a user account."""
        credit_key = self._credit_key(user_account_key)
        new_amount = yield self.redis.incr(credit_key, amount)
        returnValue(new_amount)

    @Manager.calls_manager
    def debit(self, user_account_key, amount):
        """Remove an amount of credits from a user account."""
        credit_key = self._credit_key(user_account_key)
        new_amount = yield self.redis.incr(credit_key, -amount)
        success = new_amount >= 0
        if not success:
            yield self.redis.incr(credit_key, amount)
        returnValue(success)

    def _credit_key(self, user_account_key):
        return ":".join(["credits", user_account_key])
