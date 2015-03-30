""" Billing utils that require Django. """

import json

from django.core import serializers

from go.billing.utils import JSONEncoder
from go.billing.models import Transaction


class TransactionSerializer(object):
    """ Helper for serializing transaction objects to JSON. """

    def __init__(self):
        self._simplifier_cls = serializers.get_serializer("python")

    def to_json(self, transactions):
        simplifier = self._simplifier_cls()
        return (json.dumps(t, cls=JSONEncoder)
                for t in simplifier.serialize(transactions))


def load_account_credits(account, credit_amount):
    # Create a new transaction
    transaction = Transaction.objects.create(
        account_number=account.account_number,
        transaction_type=Transaction.TRANSACTION_TYPE_TOPUP,
        credit_amount=credit_amount)

    # Update the selected account's credit balance
    account.credit_balance += transaction.credit_amount
    account.last_topup_balance = account.credit_balance
    account.save()

    # Update the transaction's status to Completed
    transaction.status = Transaction.STATUS_COMPLETED
    transaction.save()
