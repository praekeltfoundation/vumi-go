from django import template
register = template.Library()


@register.filter(name='attr_class')
def attr_class(field, class_names):
    return field.as_widget(attrs={'class': class_names})
