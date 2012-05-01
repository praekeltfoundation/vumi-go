# -*- test-case-name: go.vumitools.tests.test_credit -*-


class CreditManager(object):
    def __init__(self, r_server, r_prefix):
        self.r_server = r_server
        self.r_prefix = r_prefix

    def get_credit(self, user_account_key):
        """Return the amount of credit available.

        :returns:
           Number of credits available (or None if the user isn't in
           the credit store yet).
        """
        credit_key = self._credit_key(user_account_key)
        credit = self.r_server.get(credit_key)
        if credit is not None:
            credit = int(credit)
        return credit

    def credit(self, user_account_key, amount):
        """Add an amount of credits to a user account."""
        credit_key = self._credit_key(user_account_key)
        new_amount = self.r_server.incr(credit_key, amount)
        return new_amount

    def debit(self, user_account_key, amount):
        """Remove an amount of credits from a user account."""
        credit_key = self._credit_key(user_account_key)
        new_amount = self.r_server.incr(credit_key, -amount)
        success = new_amount >= 0
        if not success:
            self.r_server.incr(credit_key, amount)
        return success

    def _credit_key(self, user_account_key):
        return ":".join([self.r_prefix, "credits", user_account_key])
