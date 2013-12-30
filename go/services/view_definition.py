from django.core.urlresolvers import reverse
from django.views.generic import View, TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, Http404


class ServiceViewMixin(object):
    """View mixin for service views"""

    view_name = None
    path_suffix = None
    csrf_exempt = False
    view_def = None

    def redirect_to(self, view_name, **kwargs):
        """Return an HTTP redirect to the given ``view_name``"""
        return redirect(self.get_view_url(view_name, **kwargs))

    def get_view_url(self, view_name, **kwargs):
        """Return the URL for the given ``view_name``"""
        return self.view_def.get_view_url(view_name, **kwargs)


class ServiceView(ServiceViewMixin, View):
    """Base class for service views"""
    pass


class ServiceTemplateView(ServiceViewMixin, TemplateView):
    """Base class for service template views"""

    template_base = 'services'

    def get_template_names(self):
        return [self.get_template_name(self.view_name)]

    def get_template_name(self, view_name):
        """Return the full template name"""
        return '%s/%s/%s.html' % (self.template_base,
                                  self.view_def.service_type, view_name)


class ServiceViewDefinitionBase(object):
    """Base class for a service view definition"""

    views = ()

    def __init__(self, service_def=None):
        self._service_def = service_def
        self._view_mapping = {}
        self._path_suffix_mapping = {}
        for view in self.views:
            self._view_mapping[view.view_name] = view
            self._path_suffix_mapping[view.path_suffix] = view

    @property
    def service_type(self):
        return self._service_def.service_type

    @property
    def service_display_name(self):
        return self._service_def.service_display_name

    def get_view_url(self, view_name, **kwargs):
        """Return the URL for the given ``view_name``"""
        kwargs['service_type'] = self._service_def.service_type
        view = self._view_mapping[view_name]
        if view.path_suffix:
            kwargs['path_suffix'] = view.path_suffix
            return reverse('services:service', kwargs=kwargs)
        else:
            return reverse('services:service_index', kwargs=kwargs)

    def get_view(self, path_suffix):
        """Return the view for the given ``path_suffix``"""
        if path_suffix not in self._path_suffix_mapping:
            raise Http404
        view_cls = self._path_suffix_mapping[path_suffix]
        view = view_cls.as_view(view_def=self)
        if view_cls.csrf_exempt:
            view = csrf_exempt(view)
        return view
