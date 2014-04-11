from django import forms


class RoutingEntryForm(forms.Form):
    endpoint = forms.CharField(
        label="Endpoint"
    )


class BaseRoutingEntryFormSet(forms.formsets.BaseFormSet):

    def __init__(self, *args, **kwargs):
        self._contact_groups = kwargs.pop('groups', [])
        super(BaseRoutingEntryFormSet, self).__init__(*args, **kwargs)

    @staticmethod
    def initial_from_config(data):
        initial = []
        for rule in data:
            initial.append({
                'group': rule['group'],
                'endpoint': rule['endpoint'],
            })
        return initial

    def to_config(self):
        rules = []
        for form in self.ordered_forms:
            if not form.is_valid():
                continue
            rules.append({
                "group": form.cleaned_data['group'],
                "endpoint": form.cleaned_data['endpoint'],
            })
        return rules

    def add_fields(self, form, index):
        super(BaseRoutingEntryFormSet, self).add_fields(form, index)
        form.fields['group'] = forms.ChoiceField(
            label="Group",
            choices=[(grp.key, grp.name) for grp in self._contact_groups],
            initial=self.initial.get(index, {}).get('group', None)
        )


RoutingEntryFormSet = forms.formsets.formset_factory(
    RoutingEntryForm,
    can_delete=True,
    extra=1,
    formset=BaseRoutingEntryFormSet)
