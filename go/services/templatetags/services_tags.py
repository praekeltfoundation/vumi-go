from django import template

from go.config import _VUMI_INSTALLED_SERVICES

register = template.Library()

# TODO: Get rid of the template tags.

for module, data in _VUMI_INSTALLED_SERVICES.iteritems():
    service_pkg = __import__(module, fromlist=['templatetags'])
    if hasattr(service_pkg, 'templatetags'):
        simple_tags = getattr(service_pkg.templatetags, 'simple_tags', [])
        for simple_tag in simple_tags:
            register.simple_tag(getattr(service_pkg.templatetags, simple_tag))
