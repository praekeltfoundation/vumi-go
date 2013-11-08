from django.core.urlresolvers import reverse

from vumi.tests.helpers import generate_proxies

from go.base.tests.helpers import DjangoVumiApiHelper
from .helpers import ApplicationHelper
from go.base import utils as base_utils


class AppViewHelper(object):
    # TODO: Avoid having to pass the TestCase in here. This requires a
    #       persistence helper which we don't have yet.
    def __init__(self, test_case, conversation_type):
        self._test_case = test_case
        self.conversation_type = conversation_type

        self.vumi_helper = DjangoVumiApiHelper(test_case)
        self._app_helper = ApplicationHelper(
            test_case, conversation_type, self.vumi_helper)
        self._app_helper.conversation_wrapper = self.get_conversation_helper

        # Create the things we need to create
        self.vumi_helper.setup_vumi_api()
        self.vumi_helper.make_django_user()

        # Proxy methods from our helpers.
        generate_proxies(self, self._app_helper)
        generate_proxies(self, self.vumi_helper)

    def cleanup(self):
        return self.vumi_helper.cleanup()

    def get_new_view_url(self):
        return reverse('conversations:new_conversation')

    def get_conversation_helper(self, conversation):
        return ConversationViewHelper(self, conversation.key)

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()


class ConversationViewHelper(object):
    def __init__(self, app_view_helper, conversation_key):
        self.conversation_key = conversation_key
        self.conversation_type = app_view_helper.conversation_type
        self.app_helper = app_view_helper

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
