from django import forms

from go.service.view_definition import (
    ServiceComponentViewDefinitionBase, EditServiceComponentView)


class MetricsServiceForm(forms.Form):
    metrics_prefix = forms.CharField()


class EditMetricsServiceForm(EditServiceComponentView):
    edit_forms = (
        (None, MetricsServiceForm),
    )


class ServiceComponentViewDefinition(ServiceComponentViewDefinitionBase):
    edit_view = EditMetricsServiceForm
