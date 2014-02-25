from django import forms


class ApplicationMultiplexerTitleForm(forms.Form):
    content = forms.CharField(
        label="Menu title",
        max_length=100
    )


class ApplicationMultiplexerForm(forms.Form):
    application_label = forms.CharField(
        label="Application label"
    )
    endpoint_name = forms.CharField(
        label="Endpoint name"
    )


class BaseApplicationMultiplexerFormSet(forms.formsets.BaseFormSet):

    @staticmethod
    def initial_from_config(data):
        initial_data = []
        for entry in data:
            initial_data.append({
                'application_label': entry['label'],
                'endpoint_name': entry['endpoint'],
            })
        return initial_data

    def to_config(self):
        entries = []
        for form in self.ordered_forms:
            if not form.is_valid():
                continue
            entries.append({
                "label": form.cleaned_data['application_label'],
                "endpoint": form.cleaned_data['endpoint_name'],
            })
        return entries


ApplicationMultiplexerFormSet = forms.formsets.formset_factory(
    ApplicationMultiplexerForm,
    can_delete=True,
    can_order=True,
    extra=1,
    formset=BaseApplicationMultiplexerFormSet)
