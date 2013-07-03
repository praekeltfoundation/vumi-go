from django import template

from go.channel.views import get_channel_view_definition


register = template.Library()


@register.simple_tag
def channel_screen(channel, view_name='show'):
    # TODO: Update this when we have proper channels.
    view_def = get_channel_view_definition(channel)
    return view_def.get_view_url(view_name, channel_key=channel.key)
