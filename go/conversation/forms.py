from django import forms

from bootstrap.forms import BootstrapForm

from go.base.utils import configured_conversation_types


class NewConversationForm(forms.Form):

    TYPE_CHOICES = configured_conversation_types().items()

    name = forms.CharField(label="Conversation name", max_length=100)
    description = forms.CharField(
        label="Conversation description", required=False)
    conversation_type = forms.ChoiceField(
        label="Which kind of conversation would you like?",
        choices=TYPE_CHOICES)


class ConfirmConversationForm(BootstrapForm):
    token = forms.CharField(required=True, widget=forms.HiddenInput)


class ConversationSearchForm(BootstrapForm):
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'input-xlarge',
        }))
    conversation_status = forms.ChoiceField(required=False,
        choices=[
            ('', 'Status ...'),
            ('running', 'Running'),
            ('finished', 'Finished'),
            ('draft', 'Draft'),
        ],
        widget=forms.Select(attrs={'class': 'input-small'}))

    def __init__(self, *args, **kw):
        conversation_types = kw.pop('conversation_types')
        super(ConversationSearchForm, self).__init__(*args, **kw)
        self.fields['conversation_type'] = forms.ChoiceField(
            required=False,
            choices=([('', 'Type ...')] + conversation_types),
            widget=forms.Select(attrs={'class': 'input-small'}))


class ReplyToMessageForm(BootstrapForm):
    in_reply_to = forms.CharField(widget=forms.HiddenInput, required=True)
    # NOTE: the to_addr is only used to display in the UI, when sending the
    #       reply the 'from_addr' of the 'in_reply_to' message copied over.
    to_addr = forms.CharField(label='Send To', required=True)
    content = forms.CharField(label='Reply Message', required=True,
        widget=forms.Textarea)
