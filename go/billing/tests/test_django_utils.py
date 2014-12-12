""" Test for go.billing.django_utils. """

import json

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper

from go.billing.models import Account
from go.billing.tests.helpers import (
    mk_transaction, get_message_credits, get_storage_credits,
    get_session_credits)

from go.billing.django_utils import TransactionSerializer


class TestTransactionSerializer(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_to_json(self):
        serializer = TransactionSerializer()
        transaction = mk_transaction(self.account)
        [datum] = serializer.to_json([transaction])
        self.assertEqual(json.loads(datum), {
            u"pk": transaction.pk,
            u"model": u"billing.transaction",
            u"fields": {
                u"account_number": self.account.account_number,
                u"created": unicode(transaction.created.isoformat()),
                u"last_modified": unicode(
                    transaction.last_modified.isoformat()),
                u"credit_amount": 28.0,
                u"credit_factor": 0.25,
                u"markup_percent": 10.0,
                u"message_cost": 100.0,
                u"storage_cost": 50.0,
                u"message_credits": float(get_message_credits(100.0, 10.0)),
                u"storage_credits": float(get_storage_credits(50.0, 10.0)),
                u"session_credits": float(get_session_credits(10.0, 10.0)),
                u"message_direction": u"Inbound",
                u"message_id": None,
                u"session_cost": 10.0,
                u"session_created": None,
                u"status": u"Completed",
                u"tag_pool_name": u"pool1",
                u"tag_name": u"tag1",
            },
        })
