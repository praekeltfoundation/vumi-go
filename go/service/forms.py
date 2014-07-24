from django import forms


class NewServiceComponentForm(forms.Form):

    name = forms.CharField(label="Service component name", max_length=100)
    description = forms.CharField(
        label="Service component description", required=False)

    def __init__(self, user_api, *args, **kwargs):
        super(NewServiceComponentForm, self).__init__(*args, **kwargs)
        service_types = user_api.service_component_types().itervalues()
        type_choices = [(service['namespace'], service['display_name'])
                        for service in service_types]
        self.fields['service_component_type'] = forms.ChoiceField(
            label="Which kind of service component would you like?",
            choices=type_choices)
