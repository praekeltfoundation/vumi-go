import logging
import urllib

from django.views.generic import View, TemplateView
from django.shortcuts import redirect, Http404
from django.core.urlresolvers import reverse
from django.contrib import messages


logger = logging.getLogger(__name__)


class ChannelViewMixin(object):
    view_name = None
    path_suffix = None

    # This is set in the constructor, but the attribute must exist already.
    view_def = None

    def redirect_to(self, name, **kwargs):
        return redirect(self.get_view_url(name, **kwargs))

    def get_view_url(self, view_name, **kwargs):
        return self.view_def.get_view_url(view_name, **kwargs)

    def get_next_view(self, channel):
        return 'show'


class ChannelTemplateView(ChannelViewMixin, TemplateView):
    template_base = 'channel'

    def get_template_names(self):
        return [self.get_template_name(self.view_name)]

    def get_template_name(self, name):
        return '%s/%s.html' % (self.template_base, name)


class ChannelApiView(ChannelViewMixin, View):
    pass


class ReleaseChannelView(ChannelApiView):
    view_name = 'release'
    path_suffix = 'release/'

    def post(self, request, channel):
        channel.release(request.user_api)
        messages.add_message(
            request, messages.INFO, '%s released' % (
                self.view_def.display_name,))
        # TODO: Go somewhere better than the conversation index.
        return redirect(reverse('conversations:index'))


class ShowChannelView(ChannelTemplateView):
    view_name = 'show'
    path_suffix = ''

    def get(self, request, channel):
        return self.render_to_response({
            'channel': channel
        })


class ChannelViewDefinitionBase(object):
    """Definition of channel UI.
    """

    # Override these params in your channel-specific subclass.
    extra_views = ()

    DEFAULT_CHANNEL_VIEWS = (
        ShowChannelView,
        ReleaseChannelView,
    )

    def __init__(self, chan_def):
        self._chan_def = chan_def

        self._views = list(self.DEFAULT_CHANNEL_VIEWS)
        self._views.extend(self.extra_views)

        self._view_mapping = {}
        self._path_suffix_mapping = {}
        for view in self._views:
            self._view_mapping[view.view_name] = view
            self._path_suffix_mapping[view.path_suffix] = view

    @property
    def display_name(self):
        return self._chan_def.display_name

    def get_view_url(self, view_name, channel_key):
        kwargs = {
            'path_suffix': self._view_mapping[view_name].path_suffix,
            'channel_key': urllib.quote(channel_key),
        }
        return reverse('channels:channel', kwargs=kwargs)

    def get_view(self, path_suffix):
        if path_suffix not in self._path_suffix_mapping:
            raise Http404
        view_cls = self._path_suffix_mapping[path_suffix]
        view = view_cls.as_view(view_def=self)
        return view
