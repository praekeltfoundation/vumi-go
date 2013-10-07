from decimal import Decimal

from django import forms
from django.forms import ModelForm
from django.forms.models import BaseModelFormSet

from go.billing.models import Account, Transaction


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
