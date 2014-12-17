""" Billing utils that require Django. """

import json

from django.core import serializers

from go.billing.utils import JSONEncoder


class TransactionSerializer(object):
    """ Helper for serializing transaction objects to JSON. """

    def __init__(self):
        self._simplifier_cls = serializers.get_serializer("python")

    def to_json(self, transactions):
        simplifier = self._simplifier_cls()
        return (json.dumps(t, cls=JSONEncoder)
                for t in simplifier.serialize(transactions))
