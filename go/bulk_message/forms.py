from django import forms
from go.conversation import models
from go.conversation.forms import ConversationForm

class BulkSendConversationForm(ConversationForm):
    """Same as the ConversationForm with the only difference being that
    this only only allows for delivery classes that allow for server
    initiated conversations."""
    delivery_class = forms.CharField(required=True, widget=forms.RadioSelect(
        attrs={'class': 'delivery-class-radio'},
        choices=[(dc,dc) for dc
                    in models.get_server_init_delivery_class_names()]))
    delivery_tag_pool = forms.CharField(required=True, widget=forms.Select(
        attrs={'class': 'input-medium'},
        choices=[(tpn, tpn) for tpn
                        in models.get_server_init_tag_pool_names()]))
