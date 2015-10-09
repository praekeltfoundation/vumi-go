""" Billing utils that require Django. """

import json
from itertools import islice, chain

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


class Summaries(object):
    """
    Helper class to summarize incrementally given model data.

    The constructor takes in a list of `select` fields and a list of `total`
    fields. Each summary corresponds to models with the same `select` fields,
    and results in a summation of those models' `total` fields.
    """

    def __init__(self, select_fields, total_fields):
        self.select_fields = select_fields
        self.total_fields = total_fields
        self.items = {}

    def incr(self, model):
        """
        Increments the :class:`Summary` matching the given model's `select`
        fields. If no matching summary is found, a new summary is created.
        """
        select_values = tuple(pick_attrs(model, self.select_fields))
        summary = self.ensure(select_values)
        summary.incr(model)
        return summary

    def ensure(self, select_values):
        """
        Gets the summary matching the given `select` values, creating and adding
        a new summary if no matching summary is found.
        """
        summary = self.items.get(select_values)

        if summary is None:
            summary = self.create(select_values)
            self.items[select_values] = summary

        return summary

    def create(self, select_values):
        """
        Creates a new summary that corresponds to the given `select` values.
        """
        return Summary(
            selects=dict(zip(self.select_fields, select_values)),
            totals=dict((field, None) for field in self.total_fields))

    def serialize(self):
        """
        Returns a list of dictionaries representing the current summary
        results.
        """
        return [
            self.items[name].serialize()
            for name in sorted(self.items.iterkeys())]


class Summary(object):
    """
    Helper class to summarize incrementally given model data by adding the given
    models' `total` fields together.
    """

    def __init__(self, selects, totals):
        self.count = 0
        self.selects = selects
        self.totals = totals

    def incr(self, model):
        """
        Adds the given model's `total` fields to the summary's current totals.
        """
        self.count = self.count + 1

        for field in self.totals.iterkeys():
            self.incr_total(field, getattr(model, field))

    def incr_total(self, field, value):
        """
        Increments the given `total` field by the given value.
        """
        if value is not None:
            current = self.totals[field]
            current = current if current is not None else 0
            self.totals[field] = value + current

    def serialize(self):
        """
        Returns a dictionary representing the current summation of `total`
        fields.
        """
        result = {'count': self.count}

        result.update(self.selects)

        result.update(dict(
            ("total_%s" % (name,), value)
            for name, value in self.totals.iteritems()))

        return result


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
            items = list(islice(iterator, items_per_chunk))
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


def summarize(queryset, select_fields, total_fields, items_per_chunk=1000):
    models = chain.from_iterable(chunked_query(queryset, items_per_chunk))
    summaries = Summaries(select_fields, total_fields)

    for model in models:
        summaries.incr(model)

    return summaries.serialize()


def pick_attrs(obj, names):
    return (getattr(obj, name) for name in names)
