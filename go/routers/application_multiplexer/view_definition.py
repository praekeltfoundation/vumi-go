from go.router.view_definition import RouterViewDefinitionBase, EditRouterView

from go.routers.application_multiplexer import \
    (ApplicationMultiplexerTitleForm, ApplicationMultiplexerFormSet)


class EditApplicationMultiplexerView(EditRouterView):
    edit_forms = (
        ('menu_title', ApplicationMultiplexerTitleForm),
        ('entries', ApplicationMultiplexerFormSet),
    )


class RouterViewDefinition(RouterViewDefinitionBase):
    edit_view = EditApplicationMultiplexerView
