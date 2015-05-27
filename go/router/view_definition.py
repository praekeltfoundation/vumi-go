import logging

from django.views.generic import View, TemplateView
from django import forms
from django.shortcuts import redirect, Http404
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages


logger = logging.getLogger(__name__)


class RouterViewMixin(object):
    view_name = None
    path_suffix = None
    csrf_exempt = False

    # This is set in the constructor, but the attribute must exist already.
    view_def = None

    def redirect_to(self, name, **kwargs):
        return redirect(self.get_view_url(name, **kwargs))

    def get_view_url(self, view_name, **kwargs):
        return self.view_def.get_view_url(view_name, **kwargs)

    def get_next_view(self, router):
        return 'show'


class RouterTemplateView(RouterViewMixin, TemplateView):
    template_base = 'router'

    def get_template_names(self):
        return [self.get_template_name(self.view_name)]

    def get_template_name(self, name):
        return '%s/%s.html' % (self.template_base, name)


class RouterApiView(RouterViewMixin, View):
    pass


class StartRouterView(RouterApiView):
    view_name = 'start'
    path_suffix = 'start/'

    def post(self, request, router):
        router_api = request.user_api.get_router_api(
            router.router_type, router.key)
        router_api.start_router()
        messages.add_message(
            request, messages.INFO, '%s started' % (
                self.view_def.router_display_name,))
        return self.redirect_to('show', router_key=router.key)


class StopRouterView(RouterApiView):
    view_name = 'stop'
    path_suffix = 'stop/'

    def post(self, request, router):
        router_api = request.user_api.get_router_api(
            router.router_type, router.key)
        router_api.stop_router()
        messages.add_message(
            request, messages.INFO, '%s stopped' % (
                self.view_def.router_display_name,))
        return self.redirect_to('show', router_key=router.key)


class ArchiveRouterView(RouterApiView):
    view_name = 'archive'
    path_suffix = 'archive/'

    def post(self, request, router):
        router_api = request.user_api.get_router_api(
            router.router_type, router.key)
        router_api.archive_router()
        messages.add_message(
            request, messages.INFO, '%s archived' % (
                self.view_def.router_display_name,))
        return redirect(reverse('routers:index'))


class ShowRouterView(RouterTemplateView):
    view_name = 'show'
    path_suffix = ''

    def get(self, request, router):
        params = {
            'router': router,
            'is_editable': self.view_def.is_editable,
        }
        templ = lambda name: self.get_template_name('includes/%s' % (name,))

        if router.archived():
            # HACK: This assumes "stopped" and "archived" are equivalent.
            params['button_template'] = templ('ended-button')
        elif router.running():
            params['button_template'] = templ('end-button')
        else:
            # TODO: Figure out better state management.
            params['button_template'] = templ('next-button')
            params['next_url'] = self.get_view_url(
                self.get_next_view(router),
                router_key=router.key)
        return self.render_to_response(params)


class EditRouterView(RouterTemplateView):
    """View for editing router data.

    Subclass this and set :attr:`edit_forms` to a list of tuples
    of the form `('key', FormClass)`.

    The `key` should be a key into the router's config field. If `key`
    is `None`, the whole of the config field will be used.

    If the default behaviour is insufficient or problematic, implement
    :meth:`make_forms` and :meth:`process_forms`. These are the only two
    methods that look at :attr:`edit_forms`.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    edit_forms = ()

    def _render_forms(self, request, router, edit_forms):
        def sum_media(form_list):
            return sum((f.media for f in form_list), forms.Media())

        return self.render_to_response({
                'router': router,
                'edit_forms_media': sum_media(edit_forms),
                'edit_forms': edit_forms,
                })

    def get(self, request, router):
        edit_forms = self.make_forms(router, request.user_api)
        return self._render_forms(request, router, edit_forms)

    def post(self, request, router):
        response = self.process_forms(request, router)
        if response is not None:
            return response

        return self.redirect_to(
            self.get_next_view(router), router_key=router.key)

    def extra_form_params(self, key, form, config, user_api):
        """
        Override this to provide extra parameters to form construction.
        """
        return {}

    def make_form(self, key, form, config, user_api):
        data = config.get(key, {})
        if hasattr(form, 'initial_from_config'):
            data = form.initial_from_config(data)
        extra = self.extra_form_params(key, form, config, user_api)
        return form(prefix=key, initial=data, **extra)

    def make_forms(self, router, user_api):
        config = router.config
        return [self.make_form(key, edit_form, config, user_api)
                for key, edit_form in self.edit_forms]

    def process_form(self, form):
        if hasattr(form, 'to_config'):
            return form.to_config()
        return form.cleaned_data

    def process_forms(self, request, router):
        config = router.config
        edit_forms_with_keys = []
        for key, form in self.edit_forms:
            extra = self.extra_form_params(key, form, config, request.user_api)
            edit_forms_with_keys.append(
                (key, form(request.POST, prefix=key, **extra)))
        edit_forms = [edit_form for _key, edit_form in edit_forms_with_keys]

        for key, edit_form in edit_forms_with_keys:
            # Is this a good idea?
            if not edit_form.is_valid():
                return self._render_forms(request, router, edit_forms)
            config[key] = self.process_form(edit_form)
        router.extra_inbound_endpoints = self.view_def.get_inbound_endpoints(
            config)
        router.extra_outbound_endpoints = self.view_def.get_outbound_endpoints(
            config)
        router.config = config
        router.save()


class RouterViewDefinitionBase(object):
    """Definition of router UI.

    Subclass this for your shiny new router and set the appropriate attributes
    and/or add special magic code.
    """

    # Override these params in your app-specific subclass.
    extra_views = ()
    edit_view = None

    DEFAULT_ROUTER_VIEWS = (
        ShowRouterView,
        StartRouterView,
        StopRouterView,
        ArchiveRouterView,
    )

    def __init__(self, router_def):
        self._router_def = router_def

        self._views = list(self.DEFAULT_ROUTER_VIEWS)
        if self.edit_view is not None:
            self._views.append(self.edit_view)
        self._views.extend(self.extra_views)

        self._view_mapping = {}
        self._path_suffix_mapping = {}
        for view in self._views:
            self._view_mapping[view.view_name] = view
            self._path_suffix_mapping[view.path_suffix] = view

    @property
    def router_display_name(self):
        return self._router_def.router_display_name

    @property
    def extra_static_inbound_endpoints(self):
        return self._router_def.extra_static_inbound_endpoints

    @property
    def extra_static_outbound_endpoints(self):
        return self._router_def.extra_static_outbound_endpoints

    def get_inbound_endpoints(self, config):
        endpoints = list(self.extra_static_inbound_endpoints)
        for endpoint in self._router_def.configured_inbound_endpoints(config):
            if (endpoint != 'default') and (endpoint not in endpoints):
                endpoints.append(endpoint)
        return endpoints

    def get_outbound_endpoints(self, config):
        endpoints = list(self.extra_static_outbound_endpoints)
        for endpoint in self._router_def.configured_outbound_endpoints(config):
            if (endpoint != 'default') and (endpoint not in endpoints):
                endpoints.append(endpoint)
        return endpoints

    @property
    def is_editable(self):
        return self.edit_view is not None

    def get_view_url(self, view_name, **kwargs):
        kwargs['path_suffix'] = self._view_mapping[view_name].path_suffix
        return reverse('routers:router', kwargs=kwargs)

    def get_view(self, path_suffix):
        if path_suffix not in self._path_suffix_mapping:
            raise Http404
        view_cls = self._path_suffix_mapping[path_suffix]
        view = view_cls.as_view(view_def=self)
        if view_cls.csrf_exempt:
            view = csrf_exempt(view)
        return view
