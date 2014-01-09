from django import template

from go.services import settings

register = template.Library()

for module, data in settings.INSTALLED_SERVICES.iteritems():
    service_pkg = __import__(module, fromlist=['templatetags'])
    if hasattr(service_pkg, 'templatetags'):
        simple_tags = getattr(service_pkg.templatetags, 'simple_tags', [])
        for simple_tag in simple_tags:
            register.simple_tag(getattr(service_pkg.templatetags, simple_tag))
