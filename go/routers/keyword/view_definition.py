from django import forms

from go.router.view_definition import RouterViewDefinitionBase, EditRouterView


class KeywordForm(forms.Form):
    keyword = forms.CharField()
    target_endpoint = forms.CharField()


class BaseKeywordFormSet(forms.formsets.BaseFormSet):
    @staticmethod
    def initial_from_config(data):
        return [{'keyword': k, 'target_endpoint': v}
                for k, v in sorted(data.items())]

    def to_config(self):
        keyword_endpoint_mapping = {}
        for form in self:
            if not form.is_valid() or form in self.deleted_forms:
                continue
            keyword = form.cleaned_data['keyword']
            target_endpoint = form.cleaned_data['target_endpoint']
            keyword_endpoint_mapping[keyword] = target_endpoint
        return keyword_endpoint_mapping


KeywordFormSet = forms.formsets.formset_factory(
    KeywordForm, can_delete=True, extra=1, formset=BaseKeywordFormSet)


class EditKeywordView(EditRouterView):
    edit_forms = (
        ('keyword_endpoint_mapping', KeywordFormSet),
    )


class RouterViewDefinition(RouterViewDefinitionBase):
    edit_view = EditKeywordView
