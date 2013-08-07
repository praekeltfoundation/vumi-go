from django import template

from go.base.utils import get_router_view_definition


register = template.Library()


@register.simple_tag
def router_screen(router, view_name='show'):
    view_def = get_router_view_definition(router.router_type, router)
    return view_def.get_view_url(view_name, router_key=router.key)
