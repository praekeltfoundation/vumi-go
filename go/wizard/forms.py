from django import forms
from django.forms.widgets import RadioSelect


class Wizard1CreateForm(forms.Form):
    CHANNEL_CHOICES = (
        ('new', 'Setup a new channel'),
        ('existing',
         'Use a keyword to route messages over an existing channel'),
    )

    channel_kind = forms.ChoiceField(label="Channels", choices=CHANNEL_CHOICES,
                                     required=False, widget=RadioSelect)
    keyword = forms.CharField(label="Define a keyword", max_length=100,
                              required=False)
    new_keyword = forms.CharField(label="Define a new keyword", max_length=100,
                                  required=False)

    def __init__(self, user_api, *args, **kwargs):
        super(Wizard1CreateForm, self).__init__(*args, **kwargs)
        keyword_router_names = [
            (router.key, router.name) for router in user_api.active_routers()
            if router.router_type == 'keyword']
        self.fields['existing_router'] = forms.ChoiceField(
            label="Select an existing keyword router",
            choices=sorted(keyword_router_names), required=False)
