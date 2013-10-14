from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class SubscriptionForm(forms.Form):
    keyword = forms.CharField()
    operation = forms.ChoiceField(choices=(
            ('subscribe', 'subscribe'),
            ('unsubscribe', 'unsubscribe'),
            ))
    campaign_name = forms.CharField()
    reply_copy = forms.CharField()


SubscriptionFormSet = forms.formsets.formset_factory(
    SubscriptionForm, can_delete=True, extra=1)


class EditSubscriptionView(EditConversationView):
    edit_forms = (
        ('handlers', SubscriptionFormSet),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditSubscriptionView
