""" Billing utils that require Django. """

import json

from django.core import serializers

from go.billing.utils import JSONEncoder


class TransactionSerializer(object):
    """ Helper for serializing transaction objects to JSON. """

    def __init__(self):
        self._simplifier = serializers.get_serializer("python")()

    def serialize(self, transactions):
        return (json.dumps(t, cls=JSONEncoder)
                for t in self._simplifier.serialize(transactions))
