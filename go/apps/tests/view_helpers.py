from django.core.urlresolvers import reverse

from zope.interface import implements

from vumi.tests.helpers import generate_proxies, IHelper

from go.base import utils as base_utils
from go.base.tests.helpers import DjangoVumiApiHelper
from go.vumitools.tests.helpers import GoMessageHelper
from .helpers import ApplicationHelper


class AppViewsHelper(object):
    implements(IHelper)

    def __init__(self, conversation_type):
        self.conversation_type = conversation_type

        self.vumi_helper = DjangoVumiApiHelper()
        self._app_helper = ApplicationHelper(
            conversation_type, self.vumi_helper)

        # Proxy methods from our helpers.
        generate_proxies(self, self._app_helper)
        generate_proxies(self, self.vumi_helper)

    def setup(self):
        # Create the things we need to create
        self.vumi_helper.setup()
        self.vumi_helper.make_django_user()

    def cleanup(self):
        return self.vumi_helper.cleanup()

    def get_new_view_url(self):
        return reverse('conversations:new_conversation')

    def get_conversation_helper(self, conversation):
        return ConversationViewHelper(self, conversation.key)

    def create_conversation_helper(self, *args, **kw):
        conversation = self.create_conversation(*args, **kw)
        return self.get_conversation_helper(conversation)

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()


class ConversationViewHelper(object):
    def __init__(self, app_views_helper, conversation_key):
        self.conversation_key = conversation_key
        self.conversation_type = app_views_helper.conversation_type
        self.app_helper = app_views_helper

    def get_view_url(self, view):
        view_def = base_utils.get_conversation_view_definition(
            self.conversation_type)
        return view_def.get_view_url(
            view, conversation_key=self.conversation_key)

    def get_action_view_url(self, action_name):
        return reverse('conversations:conversation_action', kwargs={
            'conversation_key': self.conversation_key,
            'action_name': action_name,
        })

    def get_conversation(self):
        return self.app_helper.get_conversation(self.conversation_key)

    def add_stored_inbound(self, count, **kw):
        msg_helper = GoMessageHelper(vumi_helper=self.app_helper)
        conv = self.get_conversation()
        return msg_helper.add_inbound_to_conv(conv, count, **kw)

    def add_stored_replies(self, msgs):
        msg_helper = GoMessageHelper(vumi_helper=self.app_helper)
        conv = self.get_conversation()
        return msg_helper.add_replies_to_conv(conv, msgs)
