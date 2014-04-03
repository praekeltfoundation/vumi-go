from django import forms


class GroupEditForm(forms.Form):

    groups = forms.MultipleChoiceField(
        label="Select Groups",
        choices=[]
    )

    def __init__(self, *args, **kwargs):
        groups = kwargs.pop('groups', [])
        super(GroupEditForm, self).__init__(*args, **kwargs)
        self.fields['groups'] = forms.MultipleChoiceField(
            label="Select Groups",
            choices=[(group.key, group.name) for group in groups]
        )

    @staticmethod
    def initial_from_config(data):
        return {'groups': data['groups']}

    def to_config(self):
        groups = {}
        if self.is_valid():
            groups = self.cleaned_data['groups']
        return {'groups': groups}
