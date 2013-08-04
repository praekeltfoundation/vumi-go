from django import forms


class NewRouterForm(forms.Form):

    name = forms.CharField(label="Router name", max_length=100)
    description = forms.CharField(label="Router description", required=False)

    def __init__(self, user_api, *args, **kwargs):
        super(NewRouterForm, self).__init__(*args, **kwargs)
        type_choices = [(router['namespace'], router['display_name'])
                        for router in user_api.router_types().itervalues()]
        self.fields['router_type'] = forms.ChoiceField(
            label="Which kind of router would you like?",
            choices=type_choices)
