from go.router.view_definition import RouterViewDefinitionBase, EditRouterView

from go.routers.app_multiplexer.forms import (ApplicationMultiplexerTitleForm,
                                              ApplicationMultiplexerFormSet)


class EditApplicationMultiplexerView(EditRouterView):
    edit_forms = (
        ('menu_title', ApplicationMultiplexerTitleForm),
        ('entries', ApplicationMultiplexerFormSet),
    )


class RouterViewDefinition(RouterViewDefinitionBase):
    edit_view = EditApplicationMultiplexerView
