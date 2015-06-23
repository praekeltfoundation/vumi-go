""" Billing utils that require Django. """

import json
import itertools

from django.core import serializers

from djorm_core.postgresql import server_side_cursors

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


def chunked_query(queryset, items_per_chunk=1000):
    """Iterate over a queryset using server-side cursors (if possible)
    and return lists of objects in chunks.

    :type queryset:
        Django query set.
    :param queryset:
        Query to iterate over.
    :param int items_per_chunk:
        Number of objects to include in each chunk. Default 1000.
    """
    with server_side_cursors(itersize=items_per_chunk):
        iterator = queryset.iterator()
        while True:
            items = list(itertools.islice(iterator, items_per_chunk))
            if not items:
                break
            yield items


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
