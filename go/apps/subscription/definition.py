from django import forms
from bootstrap.forms import BootstrapForm

from go.vumitools.conversation.definition import ConversationDefinitionBase


class SubscriptionForm(BootstrapForm):
    keyword = forms.CharField()
    operation = forms.ChoiceField(choices=(
            ('subscribe', 'subscribe'),
            ('unsubscribe', 'unsubscribe'),
            ))
    campaign_name = forms.CharField()
    reply_copy = forms.CharField()


SubscriptionFormSet = forms.formsets.formset_factory(
    SubscriptionForm, can_delete=True, extra=1)


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = u'subscription'

    edit_conversation_forms = (
        ('handlers', SubscriptionFormSet),
    )
