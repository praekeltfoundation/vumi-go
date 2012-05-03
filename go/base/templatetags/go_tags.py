from django import template
import string


register = template.Library()


class LoadAlphabetNode(template.Node):
    def __init__(self, var_name):
        self.var_name = var_name

    def render(self, context):
        context[self.var_name] = string.ascii_lowercase
        return ''


@register.tag
def load_alphabet(parser, token):
    try:
        tag_name, _as, var_name = token.contents.split()
    except ValueError:
        raise template.TemplateSyntaxError(
            'load_alphabet tag requires 6 arguments')
    return LoadAlphabetNode(var_name)
