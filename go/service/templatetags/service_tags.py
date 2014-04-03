from django import template

from go.base.utils import get_service_view_definition


register = template.Library()


@register.simple_tag
def service_screen(service, view_name='show'):
    view_def = get_service_view_definition(
        service.service_component_type, service)
    return view_def.get_view_url(view_name, service_key=service.key)
