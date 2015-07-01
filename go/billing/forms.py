from decimal import Decimal, Context, Inexact

from django.conf import settings
from django import forms
from django.forms import ModelForm
from django.forms.models import BaseModelFormSet

from go.vumitools.api import VumiApi

from go.billing.models import Account, TagPool, MessageCost
from go.billing.django_utils import load_account_credits


def cost_rounded_to_zero(a, context):
    """
    Return ``True`` if ``a`` was rouned to zero (and ``False`` otherwise).
    """
    return bool(context.flags[Inexact] and a == Decimal('0.0'))


class MessageCostForm(ModelForm):

    class Meta:
        model = MessageCost

    def clean(self):
        """
        Check that:

        * the resulting message credit cost does not underflow to zero.
        * the resulting session credit cost does not underflow to zero.
        * the resulting storage credit cost does not underflow to zero.
        * the resulting session unit credit cost does not underflow to zero.
        * that if the tag pool is not set, neither is the account (
          this is because our message cost lookup currently ignore
          such message costs)
        """
        cleaned_data = super(MessageCostForm, self).clean()
        message_cost = cleaned_data.get('message_cost')
        storage_cost = cleaned_data.get('storage_cost')
        session_cost = cleaned_data.get('session_cost')
        markup_percent = cleaned_data.get('markup_percent')
        session_unit_cost = cleaned_data.get('session_unit_cost')

        if message_cost and markup_percent:
            context = Context()
            credit_cost = MessageCost.calculate_message_credit_cost(
                message_cost, markup_percent, context=context)
            if cost_rounded_to_zero(credit_cost, context):
                raise forms.ValidationError(
                    "The resulting cost per message (in credits) was rounded"
                    " to 0.")

        if storage_cost and markup_percent:
            context = Context()
            credit_cost = MessageCost.calculate_storage_credit_cost(
                storage_cost, markup_percent, context=context)
            if cost_rounded_to_zero(credit_cost, context):
                raise forms.ValidationError(
                    "The resulting storage cost per message (in credits) was "
                    "rounded to 0.")

        if session_cost and markup_percent:
            context = Context()
            session_credit_cost = MessageCost.calculate_session_credit_cost(
                session_cost, markup_percent, context=context)
            if cost_rounded_to_zero(session_credit_cost, context):
                raise forms.ValidationError(
                    "The resulting cost per session (in credits) was rounded"
                    " to 0.")

        if session_unit_cost and markup_percent:
            context = Context()
            credit_cost = MessageCost.calculate_session_unit_credit_cost(
                session_unit_cost, markup_percent, context=context)
            if cost_rounded_to_zero(credit_cost, context):
                raise forms.ValidationError(
                    "The resulting cost per session time length (in credits)"
                    " was rounded to 0.")

        if not cleaned_data.get("tag_pool") and cleaned_data.get("account"):
            raise forms.ValidationError(
                "Message costs with an empty tag pool value and a non-empty"
                " account value are not currently supported by the billing"
                " API's message cost look up.")

        return cleaned_data


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
        load_account_credits(self.instance, self.cleaned_data['credit_amount'])

    class Meta:
        model = Account


class TagPoolForm(ModelForm):

    class Meta:
        model = TagPool

    def __init__(self, *args, **kwargs):
        super(TagPoolForm, self).__init__(*args, **kwargs)
        name_choices = [('', '---------')]
        api = VumiApi.from_config_sync(settings.VUMI_API_CONFIG)
        try:
            for pool_name in api.tpm.list_pools():
                name_choices.append((pool_name, pool_name))
        finally:
            api.close()
        self.fields['name'] = forms.ChoiceField(choices=name_choices)
