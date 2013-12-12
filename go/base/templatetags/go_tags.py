from urlparse import parse_qs

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
def add_params(request, params=None, **kwargs):
    """Reconstruct the URL parameters by adding any extra params.

    ``params`` can either be a query string or a *dict* mapping parameter
    names to values.
    """
    query = request.GET.copy()
    if params:
        if isinstance(params, basestring):
            params = parse_qs(params)
        params.update(kwargs)
    else:
        params = kwargs
    for k, v in params.iteritems():
        if isinstance(v, list):
            query.setlist(k, v)
        else:
            query[k] = v
    return query.urlencode(query)
