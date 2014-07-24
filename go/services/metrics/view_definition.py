import json

from django import forms

from go.service.view_definition import (
    ServiceComponentViewDefinitionBase, EditServiceComponentView)


class MetricsServiceForm(forms.Form):
    metrics_prefix = forms.CharField()
    # TODO: Figure out an appropriate penance for the following.
    metrics_json = forms.CharField(widget=forms.Textarea, required=False)

    @staticmethod
    def initial_from_config(data):
        return {
            'metrics_prefix': data.get('metrics_prefix', ''),
            'metrics_json': json.dumps(data.get('metrics', [])),
        }

    def to_config(self):
        return {
            'metrics_prefix': self.cleaned_data['metrics_prefix'],
            'metrics': json.loads(self.cleaned_data['metrics_json']),
        }


class EditMetricsServiceView(EditServiceComponentView):
    edit_forms = (
        (None, MetricsServiceForm),
    )


class ServiceComponentViewDefinition(ServiceComponentViewDefinitionBase):
    edit_view = EditMetricsServiceView
