from decimal import Decimal, Context

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.billing import settings as app_settings
from go.billing.forms import (
    MessageCostForm, cost_rounded_to_zero)
from go.billing.models import TagPool, Account


class TestBillingFormsModule(GoDjangoTestCase):
    def test_cost_rounded_to_zero(self):
        for value, result in [
                ('1.0', False), ('0.0', False),
                ('0.1', False), ('0.05', True),
                ]:
            context = Context()
            d = Decimal(value).quantize(Decimal('0.1'), context=context)
            if result:
                self.assertTrue(cost_rounded_to_zero(d, context),
                                "value was %r" % (value,))
            else:
                self.assertFalse(cost_rounded_to_zero(d, context),
                                 "value was %r" % (value,))


class TestMessageCostForm(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user = self.user_helper.get_django_user()

        self.tag_pool = TagPool(name=u"pool", description=u"description")
        self.tag_pool.save()

        self.account = Account.objects.get(user=self.user)

    def patch_quantization(self, quantization):
        self.monkey_patch(
            app_settings, 'QUANTIZATION_EXPONENT', quantization)

    def mk_form(self, **kw):
        data = {
            'tag_pool': self.tag_pool.pk,
            'message_direction': 'Inbound',
            'message_cost': '0.0',
            'session_cost': '0.0',
            'markup_percent': '0.0',
        }
        data.update(kw)
        return MessageCostForm(data=data)

    def test_validate_no_costs(self):
        mc = self.mk_form(markup_percent='10.0')
        self.assertTrue(mc.is_valid())

    def test_validate_message_cost_not_rounded_to_zero(self):
        mc = self.mk_form(message_cost='1.0', markup_percent='10.0')
        self.assertTrue(mc.is_valid())

    def test_validate_message_cost_rounded_to_zero(self):
        self.patch_quantization(Decimal('0.1'))
        mc = self.mk_form(message_cost='0.001',
                          markup_percent='0.1')
        self.assertFalse(mc.is_valid())
        self.assertEqual(mc.errors, {
            '__all__': [
                'The resulting cost per message (in credits) was rounded'
                ' to 0.',
            ],
        })

    def test_validate_session_cost_not_rounded_to_zero(self):
        mc = self.mk_form(session_cost='1.0', markup_percent='10.0')
        self.assertTrue(mc.is_valid())

    def test_validate_session_cost_rounded_to_zero(self):
        self.patch_quantization(Decimal('0.1'))
        mc = self.mk_form(session_cost='0.001',
                          markup_percent='0.1')
        self.assertFalse(mc.is_valid())
        self.assertEqual(mc.errors, {
            '__all__': [
                'The resulting cost per session (in credits) was rounded'
                ' to 0.',
            ],
        })

    def test_validate_no_account_and_no_tag_pool(self):
        mc = self.mk_form(account=None, tag_pool=None)
        self.assertTrue(mc.is_valid())

    def test_validate_account_and_no_tag_pool(self):
        mc = self.mk_form(account=self.account.pk, tag_pool=None)
        self.assertFalse(mc.is_valid())
        self.assertEqual(mc.errors, {
            '__all__': [
                "Message costs with an empty tag pool value and a non-empty"
                " account value are not currently supported by the billing"
                " API's message cost look up.",
            ],
        })
