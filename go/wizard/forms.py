from django import forms
from django.forms.widgets import RadioSelect


class Wizard1CreateForm(forms.Form):
    CHANNEL_CHOICES = (
        ('new', 'Setup a new channel'),
        ('existing',
         'Use a keyword to route messages over an existing channel'),
    )

    channel_kind = forms.ChoiceField(label="Channels", choices=CHANNEL_CHOICES,
                                     widget=RadioSelect)
    keyword = forms.CharField(label="Define a keyword", max_length=100,
                              required=False)


class Wizard1ExistingRouterForm(forms.Form):
    new_keyword = forms.CharField(label="Define a new keyword", max_length=100)

    def __init__(self, user_api, *args, **kwargs):
        super(Wizard1ExistingRouterForm, self).__init__(*args, **kwargs)
        keyword_routers = [router for router in user_api.active_routers()
                           if router.router_type == 'keyword']
        self.router_keywords = dict(
            (kwr.key, kwr.config.get('keyword_endpoint_mapping', {}).keys())
            for kwr in keyword_routers)
        keyword_router_names = [(r.key, r.name) for r in keyword_routers]
        self.fields['existing_router'] = forms.ChoiceField(
            label="Select an existing keyword router",
            choices=sorted(keyword_router_names))

    def clean(self):
        cleaned_data = super(Wizard1ExistingRouterForm, self).clean()
        existing_router = cleaned_data.get('existing_router')
        new_keyword = cleaned_data.get('new_keyword')
        if new_keyword and existing_router and (
                new_keyword in self.router_keywords[existing_router]):
            self._errors['new_keyword'] = self.error_class(
                ['Existing keywords may not be reused'])
            del cleaned_data['new_keyword']
        return cleaned_data
