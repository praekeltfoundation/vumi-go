from go.router.view_definition import RouterViewDefinitionBase, EditRouterView

from go.routers.group.forms import GroupEditForm
from go.vumitools.contact import ContactStore


class EditGroupRouterView(EditRouterView):

    edit_forms = (
        ('config', GroupEditForm),
    )

    def retrieve_contact_groups(self, user_account):
        contact_store = ContactStore.from_user_account(user_account)
        groups = contact_store.list_groups()
        return groups

    def make_forms(self, router):
        config = router.config
        return [self.make_form(router, key, edit_form, config)
                for key, edit_form in self.edit_forms]

    def make_form(self, router, key, form, metadata):
        data = metadata.get(key, {})
        if hasattr(form, 'initial_from_config'):
            data = form.initial_from_config(data)
        groups = self.retrieve_contact_groups(router.user_account)
        return form(prefix=key, initial=data, groups=groups)


class RouterViewDefinition(RouterViewDefinitionBase):
    edit_view = EditGroupRouterView
