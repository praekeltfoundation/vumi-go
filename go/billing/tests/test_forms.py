from decimal import Decimal, Context

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.forms.models import modelformset_factory

    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.billing import settings as app_settings
    from go.billing.forms import (
        MessageCostForm, cost_rounded_to_zero, BaseCreditLoadFormSet,
        CreditLoadForm, TagPoolForm)
    from go.billing.models import TagPool, Account, Transaction


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
            'storage_cost': '0.0',
            'session_cost': '0.0',
            'session_unit_cost': '0.0',
            'session_unit_length': '0.0',
            'session_unit_time': '0.0',
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

    def test_validate_storage_cost_not_rounded_to_zero(self):
        mc = self.mk_form(storage_cost='1.0', markup_percent='10.0')
        self.assertTrue(mc.is_valid())

    def test_validate_storage_cost_rounded_to_zero(self):
        self.patch_quantization(Decimal('0.1'))
        mc = self.mk_form(storage_cost='0.001',
                          markup_percent='0.1')
        self.assertFalse(mc.is_valid())
        self.assertEqual(mc.errors, {
            '__all__': [
                'The resulting storage cost per message (in credits) was'
                ' rounded to 0.',
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

    def test_validate_session_length_cost_not_rounded_to_zero(self):
        mc = self.mk_form(session_unit_cost='1.0', markup_percent='10.0')
        self.assertTrue(mc.is_valid())

    def test_validate_session_length_cost_rounded_to_zero(self):
        self.patch_quantization(Decimal('0.1'))
        mc = self.mk_form(session_unit_cost='0.001', markup_percent='0.1')
        self.assertFalse(mc.is_valid())
        self.assertEqual(mc.errors, {
            '__all__': [
                'The resulting cost per session time length (in credits) was'
                ' rounded to 0.',
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


class TestCreditLoadForm(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user = self.user_helper.get_django_user()

        self.account = Account.objects.get(user=self.user)

    def mk_formset(self, **kw):
        CreditLoadFormSet = modelformset_factory(
            Account, form=CreditLoadForm, formset=BaseCreditLoadFormSet,
            fields=('account_number',), extra=0)

        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-0-id': self.account.id,
            'form-0-account_number': self.account.account_number,
            'form-0-credit_amount': '10',
        }
        data.update(kw)

        queryset = Account.objects.filter(pk=self.account.pk)
        formset = CreditLoadFormSet(data, queryset=queryset)
        return formset

    def test_load_credits(self):
        self.account.last_topup_balance = Decimal('20.0')
        self.account.save()

        formset = self.mk_formset()
        self.assertTrue(formset.is_valid())
        [form] = list(formset)

        self.assertEqual(self.account.credit_balance, Decimal('0.0'))
        self.assertEqual(self.account.last_topup_balance, Decimal('20.0'))

        form.load_credits()

        account = Account.objects.get(user=self.user)
        self.assertEqual(account.credit_balance, Decimal('10.0'))
        self.assertEqual(account.last_topup_balance, Decimal('10.0'))

        [transaction] = Transaction.objects.filter(
            account_number=self.account.account_number).all()
        self.assertEqual(transaction.status, Transaction.STATUS_COMPLETED)
        self.assertEqual(transaction.credit_amount, Decimal('10.0'))


class TestTagPoolForm(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.vumi_helper.setup_tagpool('pool', ['tag-1', 'tag-2'])

    def mk_form(self, **kw):
        data = {
            'name': 'pool',
            'description': 'A dummy tag pool',
        }
        data.update(kw)
        return TagPoolForm(data=data)

    def test_name_choices(self):
        form = TagPoolForm()
        self.assertEqual(form.fields['name'].choices, [
            ('', '---------'),
            ('pool', 'pool'),
        ])

    def test_valid_form(self):
        form = self.mk_form()
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        form = self.mk_form(name='unknown')
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'name': [
                'Select a valid choice. unknown is not one of the available'
                ' choices.',
            ]
        })
