from django import forms

from go.conversation.base import ConversationViews


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


class SubscriptionConversationViews(ConversationViews):
    conversation_type = u'subscription'
    conversation_initiator = u'client'
    edit_conversation_forms = (
        ('handlers', SubscriptionFormSet),
        )
