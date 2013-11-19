from django import template
register = template.Library()


@register.filter(name='attr_class')
def attr_class(field, class_names):
    return field.as_widget(attrs={'class': class_names})


@register.filter(name='split')
def split(value, delimiter):
    """The opposite of the ``join`` template tag"""
    return value.split(delimiter)


@register.simple_tag
def add_params(request, params_dict=None, **kwargs):
    """Reconstruct the URL parameters by adding any extras passed in to
       ``kwargs``.
    """
    query = request.GET.copy()
    if params_dict:
        params_dict.update(kwargs)
    else:
        params_dict = kwargs
    for k, v in params_dict.iteritems():
        if isinstance(v, list):
            query.setlist(k, v)
        else:
            query[k] = v
    return query.urlencode(query)


@register.assignment_tag
def get_param(request, name, default=''):
    """Get the URL parameter value.

    If the value is list return a CSV string.
    """
    value = request.GET.getlist(name)
    if value:
        value.sort()
        return ','.join(value)
    return default
