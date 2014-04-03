from django import forms

from go.service.view_definition import (
    ServiceComponentViewDefinitionBase, EditServiceComponentView)


class RedisKVStoreForm(forms.Form):
    key_expiry_time = forms.IntegerField()


class EditRedisKVStoreForm(EditServiceComponentView):
    edit_forms = (
        (None, RedisKVStoreForm),
    )


class ServiceComponentViewDefinition(ServiceComponentViewDefinitionBase):
    edit_view = EditRedisKVStoreForm
