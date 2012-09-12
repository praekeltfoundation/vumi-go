from datetime import datetime

from django.views.generic import TemplateView

from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.conf.urls.defaults import url, patterns

from go.vumitools.exceptions import ConversationSendError
from go.conversation.forms import ConversationForm, ConversationGroupForm
from go.base.utils import make_read_only_form, conversation_or_404


class ConversationView(TemplateView):
    template_name = None
    template_base = 'generic'

    # These are overridden on construction.
    conversation_form = None
    conversation_group_form = None
    conversation_type = None
    conversation_initiator = None
    conversation_display_name = None
    tagpool_filter = None

    def request_setup(self, request, conversation_key):
        """Perform common request setup.

        By default, expects a conversation key and fetches the appropriate
        conversation.
        """
        conversation = conversation_or_404(request.user_api, conversation_key)
        return (conversation,), {}

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        args, kwargs = self.request_setup(request, *args, **kwargs)
        return super(ConversationView, self).dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return ['%s/%s.html' % (self.template_base, self.template_name)]

    def redirect_to(self, name, **kwargs):
        return redirect(
            reverse('%s:%s' % (self.conversation_type, name), kwargs=kwargs))

    def make_conversation_form(self, *args, **kw):
        kw.setdefault('tagpool_filter', self.tagpool_filter)
        return self.conversation_form(*args, **kw)


class NewConversationView(ConversationView):
    template_name = 'new'

    def request_setup(self, request):
        return (), {}

    def get(self, request):
        # We used to put the time in the form, but that's a silly thing to do.
        # Especially since we now ignore it anyway.
        form = self.make_conversation_form(request.user_api, initial={})
        return self.render_to_response({'form': form})

    def post(self, request):
        form = self.make_conversation_form(request.user_api, request.POST)
        if not form.is_valid():
            return self.render_to_response({'form': form})

        copy_keys = [
            'subject',
            'message',
            'delivery_class',
            'delivery_tag_pool',
            ]
        conversation_data = dict((k, form.cleaned_data[k]) for k in copy_keys)

        tag_info = form.cleaned_data['delivery_tag_pool'].partition(':')
        conversation_data['delivery_tag_pool'] = tag_info[0]
        if tag_info[2]:
            conversation_data['delivery_tag'] = tag_info[2]

        # Ignoring start time, because we don't actually do anything with it.
        conversation_data['start_timestamp'] = datetime.utcnow()

        conversation = request.user_api.new_conversation(
            self.conversation_type, **conversation_data)
        messages.add_message(request, messages.INFO,
                             '%s Created' % (self.conversation_display_name,))

        if self.conversation_initiator == 'client':
            return self.redirect_to('start', conversation_key=conversation.key)
        return self.redirect_to('people', conversation_key=conversation.key)


class PeopleConversationView(ConversationView):
    template_name = 'people'

    def request_setup(self, request, conversation_key):
        conversation = conversation_or_404(request.user_api, conversation_key)
        groups = request.user_api.list_groups()
        return (conversation, groups), {}

    def get(self, request, conversation, groups):
        conversation_form = make_read_only_form(self.make_conversation_form(
                request.user_api, instance=conversation, initial={
                    'start_date': conversation.start_timestamp.date(),
                    'start_time': conversation.start_timestamp.time(),
                    }))
        return self.render_to_response({
                'conversation': conversation,
                'conversation_form': conversation_form,
                'groups': groups,
                })

    def post(self, request, conversation, groups):
        group_form = self.conversation_group_form(request.POST, groups=groups)
        if not group_form.is_valid():
            return self.get(request, conversation, groups)

        for group in group_form.cleaned_data['groups']:
            conversation.groups.add_key(group)
        conversation.save()
        messages.add_message(request, messages.INFO,
            'The selected groups have been added to the conversation')
        return self.redirect_to('start', conversation_key=conversation.key)


class StartConversationView(ConversationView):
    template_name = 'start'

    def get(self, request, conversation):
        conversation_form = make_read_only_form(self.make_conversation_form(
                request.user_api, instance=conversation, initial={}))
        groups = request.user_api.list_groups()
        group_form = make_read_only_form(
            self.conversation_group_form(groups=groups))

        if self.conversation_initiator == 'client':
            return self.render_to_response({
                    'send_messages': False,
                    'conversation': conversation,
                    })

        return self.render_to_response({
                'send_messages': True,
                'conversation': conversation,
                'conversation_form': conversation_form,
                'group_form': group_form,
                'groups': conversation.groups.get_all(),
                'people': conversation.people(),
                })

    def post(self, request, conversation):
        params = {}
        if self.conversation_initiator != 'client':
            params['dedupe'] = request.POST.get('dedupe') == '1'
        try:
            conversation.start(**params)
        except ConversationSendError as error:
            messages.add_message(request, messages.ERROR, str(error))
            return self.redirect_to('start', conversation_key=conversation.key)
        messages.add_message(request, messages.INFO,
                             '%s started' % (self.conversation_display_name,))
        return self.redirect_to('show', conversation_key=conversation.key)


class ShowConversationView(ConversationView):
    template_name = 'show'

    def get(self, request, conversation):
        return self.render_to_response({
                'conversation': conversation,
                })


class EndConversationView(ConversationView):
    def post(self, request, conversation):
        if request.method == 'POST':
            conversation.end_conversation()
            messages.add_message(
                request, messages.INFO,
                '%s ended' % (self.conversation_display_name,))
        return self.redirect_to('show', conversation_key=conversation.key)


def tf_server_initiated(pool, metadata):
    return metadata.get('server_initiated', False)


def tf_client_initiated(pool, metadata):
    return metadata.get('client_initiated', False)


class ConversationViews(object):
    new_conversation_view = NewConversationView
    people_conversation_view = PeopleConversationView
    start_conversation_view = StartConversationView
    show_conversation_view = ShowConversationView
    end_conversation_view = EndConversationView

    conversation_form = ConversationForm
    conversation_group_form = ConversationGroupForm
    conversation_type = None
    tagpool_filter = None
    # This can be "client", "server" or None.
    conversation_initiator = None
    conversation_display_name = 'Conversation'

    def mkview(self, name):
        cls = getattr(self, '%s_conversation_view' % (name,))
        if self.tagpool_filter is None:
            self.tagpool_filter = {
                'server': tf_server_initiated,
                'client': tf_client_initiated,
                None: None,
                }[self.conversation_initiator]
        return cls.as_view(
            conversation_form=self.conversation_form,
            conversation_group_form=self.conversation_group_form,
            conversation_type=self.conversation_type,
            tagpool_filter=self.tagpool_filter,
            conversation_initiator=self.conversation_initiator,
            conversation_display_name=self.conversation_display_name)

    def mkurl(self, name, regex=None):
        if regex is None:
            regex = r'^(?P<conversation_key>\w+)/%s/' % (name,)
        return url(regex, self.mkview(name), name=name)

    def get_urlpatterns(self):
        urls = [
            self.mkurl('new', r'^new/'),
            self.mkurl('start'),
            self.mkurl('end'),
            self.mkurl('show', r'^(?P<conversation_key>\w+)/$'),
            ] + self.extra_urls()
        if self.conversation_initiator != 'client':
            urls.append(self.mkurl('people'))
        return patterns('', *urls)

    def extra_urls(self):
        return []
