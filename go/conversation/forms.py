from django import forms

from bootstrap.forms import BootstrapForm


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
