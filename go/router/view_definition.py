import logging

from django.views.generic import View, TemplateView
from django import forms
from django.shortcuts import redirect, Http404
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt


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
        raise NotImplementedError('TODO')


class StopRouterView(RouterApiView):
    view_name = 'stop'
    path_suffix = 'stop/'

    def post(self, request, router):
        raise NotImplementedError('TODO')


class ArchiveRouterView(RouterApiView):
    view_name = 'archive'
    path_suffix = 'archive/'

    def post(self, request, conversation):
        raise NotImplementedError('TODO')


class ShowRouterView(RouterTemplateView):
    view_name = 'show'
    path_suffix = ''

    def get(self, request, router):
        params = {
            'router': router,
            'is_editable': self.view_def.is_editable,
            'user_api': request.user_api,
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
    """View for editing conversation data.

    Subclass this and set :attr:`edit_forms` to a list of tuples
    of the form `('key', FormClass)`.

    The `key` should be a key into the conversation's metadata field. If `key`
    is `None`, the whole of the metadata field will be used.

    If the default behaviour is insufficient or problematic, implement
    :meth:`make_forms` and :meth:`process_forms`. These are the only two
    methods that look at :attr:`edit_forms`.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    edit_forms = ()

    def _render_forms(self, request, conversation, edit_forms):
        def sum_media(form_list):
            return sum((f.media for f in form_list), forms.Media())

        return self.render_to_response({
                'conversation': conversation,
                'edit_forms_media': sum_media(edit_forms),
                'edit_forms': edit_forms,
                })

    def get(self, request, conversation):
        edit_forms = self.make_forms(conversation)
        return self._render_forms(request, conversation, edit_forms)

    def post(self, request, conversation):
        response = self.process_forms(request, conversation)
        if response is not None:
            return response

        return self.redirect_to(self.get_next_view(conversation),
                                conversation_key=conversation.key)

    def make_form(self, key, form, metadata):
        data = metadata.get(key, {})
        if hasattr(form, 'initial_from_metadata'):
            data = form.initial_from_metadata(data)
        return form(prefix=key, initial=data)

    def make_forms(self, conversation):
        config = conversation.get_config()
        return [self.make_form(key, edit_form, config)
                for key, edit_form in self.edit_forms]

    def process_form(self, form):
        if hasattr(form, 'to_metadata'):
            return form.to_metadata()
        return form.cleaned_data

    def process_forms(self, request, conversation):
        config = conversation.get_config()
        edit_forms_with_keys = [
            (key, edit_form_cls(request.POST, prefix=key))
            for key, edit_form_cls in self.edit_forms]
        edit_forms = [edit_form for _key, edit_form in edit_forms_with_keys]

        for key, edit_form in edit_forms_with_keys:
            # Is this a good idea?
            if not edit_form.is_valid():
                return self._render_forms(request, conversation, edit_forms)
            config[key] = self.process_form(edit_form)
        conversation.set_config(config)
        conversation.save()


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
