from django import forms

from go.router.view_definition import RouterViewDefinitionBase, EditRouterView
from go.routers.app_multiplexer.common import mkmenu


class ApplicationMultiplexerTitleForm(forms.Form):
    menu_title = forms.CharField(
        label="Menu Title",
        max_length=29
    )


class ApplicationMultiplexerForm(forms.Form):
    application_title = forms.CharField(
        label="Application Title",
    )
    target_endpoint = forms.CharField(
        label="Endpoint"
    )


class BaseApplicationMultiplexerFormSet(forms.formsets.BaseFormSet):

    # TODO: move to a config file if appropriate
    # We reserve 130 chars for the menu and 29 chars for the title or
    # description of the menu

    MENU_CHAR_LENGTH = 130

    def clean(self):
        """
        Checks that no two applications have the same title.

        We need to verify that application names, and endpoint
        names are unique. Also throwing message size check for USSD.
        """
        if any(self.errors):
            return

        # (Title, Endpoint) uniqueness check
        titles = []
        endpoints = []
        for i in range(0, self.total_form_count()):
            title = self.forms[i].cleaned_data['application_title']
            endpoint = self.forms[i].cleaned_data['target_endpoint']
            if title in titles or endpoint in endpoints:
                raise forms.ValidationError(
                    "Application titles and endpoints should be distinct."
                )
            titles.append(title)
            endpoints.append(endpoint)

        # Menu size check for the benefit of USSD which is usually limited
        # to 160 chars
        if len(mkmenu(titles)) > self.MENU_CHAR_LENGTH:
            raise forms.ValidationError(
                "The generated menu is too large. Either reduce the length of "
                "application titles or the number of applications."
            )

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
