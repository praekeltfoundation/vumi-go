from go.router.view_definition import RouterViewDefinitionBase, EditRouterView

from go.routers.group.forms import RoutingEntryFormSet


class GroupRouterEditView(EditRouterView):

    edit_forms = (
        ('rules', RoutingEntryFormSet),
    )

    def extra_form_params(self, key, form, config, user_api):
        return {'groups': user_api.list_groups()}


class RouterViewDefinition(RouterViewDefinitionBase):
    edit_view = GroupRouterEditView
