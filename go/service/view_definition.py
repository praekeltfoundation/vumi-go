from django import forms
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.views.generic import View, TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, Http404


class ServiceComponentViewMixin(object):
    """View mixin for service views"""

    view_name = None
    path_suffix = None
    csrf_exempt = False
    view_def = None

    @property
    def service_def(self):
        return self.view_def.service_def

    def redirect_to(self, view_name, **kwargs):
        """Return an HTTP redirect to the given ``view_name``"""
        return redirect(self.get_view_url(view_name, **kwargs))

    def get_view_url(self, view_name, **kwargs):
        """Return the URL for the given ``view_name``"""
        return self.view_def.get_view_url(view_name, **kwargs)

    def get_next_view(self, service):
        return 'show'


class ServiceComponentApiView(ServiceComponentViewMixin, View):
    """Base class for service API views"""


class ServiceComponentTemplateView(ServiceComponentViewMixin, TemplateView):
    """Base class for service template views"""

    template_base = 'service'

    def get_template_names(self):
        return [self.get_template_name(self.view_name)]

    def get_template_name(self, view_name):
        """Return the full template name"""
        return '%s/%s.html' % (self.template_base, view_name)


class StartServiceComponentView(ServiceComponentApiView):
    view_name = 'start'
    path_suffix = 'start/'

    def post(self, request, service):
        service_api = request.user_api.get_service_component_api(
            service.service_component_type, service.key)
        service_api.start_service()
        messages.add_message(
            request, messages.INFO, '%s started' % (
                self.view_def.service_component_display_name,))
        return self.redirect_to('show', service_key=service.key)


class StopServiceComponentView(ServiceComponentApiView):
    view_name = 'stop'
    path_suffix = 'stop/'

    def post(self, request, service):
        service_api = request.user_api.get_service_component_api(
            service.service_component_type, service.key)
        service_api.stop_service()
        messages.add_message(
            request, messages.INFO, '%s stopped' % (
                self.view_def.service_component_display_name,))
        return self.redirect_to('show', service_key=service.key)


class ArchiveServiceComponentView(ServiceComponentApiView):
    view_name = 'archive'
    path_suffix = 'archive/'

    def post(self, request, service):
        service_api = request.user_api.get_service_component_api(
            service.service_component_type, service.key)
        service_api.archive_service()
        messages.add_message(
            request, messages.INFO, '%s archived' % (
                self.view_def.service_component_display_name,))
        return redirect(reverse('services:index'))


class ShowServiceComponentView(ServiceComponentTemplateView):
    view_name = 'show'
    path_suffix = ''

    def get(self, request, service):
        params = {
            'service': service,
            'is_editable': self.view_def.is_editable,
            'user_api': request.user_api,
        }
        templ = lambda name: self.get_template_name('includes/%s' % (name,))

        if service.archived():
            # HACK: This assumes "stopped" and "archived" are equivalent.
            params['button_template'] = templ('ended-button')
        elif service.running():
            params['button_template'] = templ('end-button')
        else:
            # TODO: Figure out better state management.
            params['button_template'] = templ('next-button')
            params['next_url'] = self.get_view_url(
                self.get_next_view(service),
                service_key=service.key)
        return self.render_to_response(params)


class EditServiceComponentView(ServiceComponentTemplateView):
    """
    View for editing service component data.

    Subclass this and set :attr:`edit_forms` to a list of tuples
    of the form `('key', FormClass)`.

    The `key` should be a key into the service component's config field. If
    `key` is `None`, the whole of the config field will be used.

    If the default behaviour is insufficient or problematic, implement
    :meth:`make_forms` and :meth:`process_forms`. These are the only two
    methods that look at :attr:`edit_forms`.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    edit_forms = ()

    def _render_forms(self, request, service, edit_forms):
        def sum_media(form_list):
            return sum((f.media for f in form_list), forms.Media())

        return self.render_to_response({
                'service': service,
                'edit_forms_media': sum_media(edit_forms),
                'edit_forms': edit_forms,
                })

    def get(self, request, service):
        edit_forms = self.make_forms(service)
        return self._render_forms(request, service, edit_forms)

    def post(self, request, service):
        response = self.process_forms(request, service)
        if response is not None:
            return response

        return self.redirect_to(
            self.get_next_view(service), service_key=service.key)

    def make_form(self, key, form, config):
        if key is None:
            data = config
        else:
            data = config.get(key, {})
        if hasattr(form, 'initial_from_config'):
            data = form.initial_from_config(data)
        return form(prefix=key, initial=data)

    def make_forms(self, service):
        config = service.config
        return [self.make_form(key, edit_form, config)
                for key, edit_form in self.edit_forms]

    def process_form(self, form):
        if hasattr(form, 'to_config'):
            return form.to_config()
        return form.cleaned_data

    def process_forms(self, request, service):
        config = service.config
        edit_forms_with_keys = [
            (key, edit_form_cls(request.POST, prefix=key))
            for key, edit_form_cls in self.edit_forms]
        edit_forms = [edit_form for _key, edit_form in edit_forms_with_keys]

        for key, edit_form in edit_forms_with_keys:
            # Is this a good idea?
            if not edit_form.is_valid():
                return self._render_forms(request, service, edit_forms)
            if key is None:
                config = self.process_form(edit_form)
            else:
                config[key] = self.process_form(edit_form)
        service.config = config
        service.save()


class ServiceComponentViewDefinitionBase(object):
    """
    Definition of service component UI.

    Subclass this for your shiny new service component and set the appropriate
    attributes and/or add special magic code.
    """

    # Override these params in your app-specific subclass.
    extra_views = ()
    edit_view = None

    DEFAULT_SERVICE_COMPONENT_VIEWS = (
        ShowServiceComponentView,
        StartServiceComponentView,
        StopServiceComponentView,
        ArchiveServiceComponentView,
    )

    def __init__(self, service_def):
        self._service_def = service_def

        self._views = list(self.DEFAULT_SERVICE_COMPONENT_VIEWS)
        if self.edit_view is not None:
            self._views.append(self.edit_view)
        self._views.extend(self.extra_views)

        self._view_mapping = {}
        self._path_suffix_mapping = {}
        for view in self._views:
            self._view_mapping[view.view_name] = view
            self._path_suffix_mapping[view.path_suffix] = view

    @property
    def service_component_type(self):
        return self._service_def.service_component_type

    @property
    def service_component_display_name(self):
        return self._service_def.service_component_display_name

    @property
    def is_editable(self):
        return self.edit_view is not None

    def get_view_url(self, view_name, **kwargs):
        kwargs['path_suffix'] = self._view_mapping[view_name].path_suffix
        return reverse('services:service', kwargs=kwargs)

    def get_view(self, path_suffix):
        """Return the view for the given ``path_suffix``"""
        if path_suffix not in self._path_suffix_mapping:
            raise Http404
        view_cls = self._path_suffix_mapping[path_suffix]
        view = view_cls.as_view(view_def=self)
        if view_cls.csrf_exempt:
            view = csrf_exempt(view)
        return view
