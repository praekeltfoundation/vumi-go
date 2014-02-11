from django import forms

from go.router.view_definition import RouterViewDefinitionBase, EditRouterView


class ApplicationMultiplexerTitleForm(forms.Form):
    menu_title = forms.CharField(
        label="Menu Title",
        max_length=32
    )


class ApplicationMultiplexerForm(forms.Form):
    application_title = forms.CharField(
        label="Application Title",
        max_length=12
    )
    target_endpoint = forms.CharField(
        label="Endpoint"
    )


class BaseApplicationMultiplexerFormSet(forms.formsets.BaseFormSet):

    def clean(self):
        """
        Checks that no two applications have the same title.
        """
        if any(self.errors):
            return
        titles = []
        for i in range(0, self.total_form_count()):
            title = self.forms[i].cleaned_data['application_title']
            if title in titles:
                raise forms.ValidationError(
                    "Application titles must be distinct."
                )
            titles.append(title)

    @staticmethod
    def initial_from_config(data):
        return [{'application_title': k, 'target_endpoint': v}
                for k, v in sorted(data.items())]

    def to_config(self):
        mappings = {}
        for form in self.forms:
            if (not form.is_valid()) or form.cleaned_data['DELETE']:
                continue
            application_title = form.cleaned_data['application_title']
            target_endpoint = form.cleaned_data['target_endpoint']
            mappings[application_title] = target_endpoint
        return mappings


ApplicationMultiplexerFormSet = forms.formsets.formset_factory(
    ApplicationMultiplexerForm,
    can_delete=True,
    max_num=8,
    extra=1,
    can_order=True,
    formset=BaseApplicationMultiplexerFormSet)


class EditApplicationMultiplexerView(EditRouterView):
    edit_forms = (
        ('menu_title', ApplicationMultiplexerTitleForm),
        ('endpoints', ApplicationMultiplexerFormSet),
    )


class RouterViewDefinition(RouterViewDefinitionBase):
    edit_view = EditApplicationMultiplexerView
