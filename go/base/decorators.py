"""Decorator utilities."""

import functools

from django.template.response import TemplateResponse


def render_exception(exception_spec, status, title):
    """Convert an given exception into a HTML error response."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(self, request, *arg, **kw):
            try:
                return f(self, request, *arg, **kw)
            except exception_spec as err:
                return TemplateResponse(
                    request, 'error.html',
                    context={
                        'error_title': title,
                        'error_reason': unicode(err),
                    },
                    status=status)
        return wrapper
    return decorator
