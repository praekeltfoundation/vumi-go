from django import forms

from go.router.view_definition import RouterViewDefinitionBase, EditRouterView


class RoutingEntryForm(forms.Form):
    endpoint = forms.CharField(
        label="Endpoint"
    )

    def has_changed(self):
        # has_changed is only used to detect whether extra forms have
        # been altered when saving. 'group' is set in extra forms
        # because it is a choice widget without a null value. We
        # remove 'group' here so that this doesn't result in the
        # formset attempting to save extra groups that haven't been
        # modified.
        changed = self.changed_data
        if 'group' in changed:
            changed.remove('group')
        return bool(changed)


class BaseRoutingEntryFormSet(forms.formsets.BaseFormSet):

    def __init__(self, *args, **kwargs):
        groups = kwargs.pop('groups', [])
        self._group_choices = [(group.key, group.name) for group in groups
                               if not group.is_smart_group()]
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
            label="Group", choices=self._group_choices,
            help_text="Note: Smart groups are not currently supported.")


RoutingEntryFormSet = forms.formsets.formset_factory(
    RoutingEntryForm,
    can_delete=True,
    can_order=True,
    extra=1,
    formset=BaseRoutingEntryFormSet)


class GroupRouterEditView(EditRouterView):

    edit_forms = (
        ('rules', RoutingEntryFormSet),
    )

    def extra_form_params(self, key, form, config, user_api):
        return {'groups': user_api.list_groups()}


class RouterViewDefinition(RouterViewDefinitionBase):
    edit_view = GroupRouterEditView
