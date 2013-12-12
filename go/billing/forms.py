from decimal import Decimal

from django.conf import settings
from django import forms
from django.forms import ModelForm
from django.forms.models import BaseModelFormSet

from go.vumitools.api import VumiApi

from go.billing.models import Account, Transaction, TagPool


class BaseCreditLoadFormSet(BaseModelFormSet):

    def __init__(self, *args, **kwargs):
        super(BaseCreditLoadFormSet, self).__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super(BaseCreditLoadFormSet, self).add_fields(form, index)
        form.fields['credit_amount'] = forms.IntegerField()


class CreditLoadForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super(CreditLoadForm, self).__init__(*args, **kwargs)
        self.fields['account_number'].widget = forms.HiddenInput()

    def load_credits(self):
        account = self.instance

        # Create a new transaction
        transaction = Transaction.objects.create(
            account_number=account.account_number,
            credit_amount=self.cleaned_data['credit_amount'])

        # Update the selected account's credit balance
        account.credit_balance += transaction.credit_amount
        account.alert_credit_balance = account.credit_balance * \
            account.alert_threshold / Decimal(100.0)

        account.save()

        # Update the transaction's status to Completed
        transaction.status = Transaction.STATUS_COMPLETED
        transaction.save()

    class Meta:
        model = Account


class TagPoolForm(ModelForm):

    class Meta:
        model = TagPool

    def __init__(self, *args, **kwargs):
        super(TagPoolForm, self).__init__(*args, **kwargs)
        name_choices = [('', '---------')]
        api = VumiApi.from_config_sync(settings.VUMI_API_CONFIG)
        for pool_name in api.tpm.list_pools():
            name_choices.append((pool_name, pool_name))
        self.fields['name'] = forms.ChoiceField(choices=name_choices)
