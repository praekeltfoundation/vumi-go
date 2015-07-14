import json
import re
import unicodedata

from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)
from go.apps.jsbox.utils import jsbox_js_config


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.

    Borrowed and slightly modified from django.utils.text.slugify().
    """
    if not isinstance(value, unicode):
        value = value.decode('utf-8')
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


class SendJsboxAction(ConversationAction):
    action_name = 'send_jsbox'
    action_display_name = 'Trigger push messages'

    needs_confirmation = True

    needs_group = True
    needs_running = True

    def check_disabled(self):
        if self._conv.has_channel_supporting_generic_sends():
            return None
        return ("This action needs channels capable of sending"
                " messages attached to this conversation.")

    def perform_action(self, action_data):
        return self.send_command('send_jsbox', batch_id=self._conv.batch.key)


class ViewLogsAction(ConversationAction):
    action_name = 'view_logs'
    action_display_name = 'View Sandbox Logs'
    redirect_to = 'jsbox_logs'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'jsbox'
    conversation_display_name = 'Javascript App'

    actions = (
        SendJsboxAction,
        ViewLogsAction,
    )

    @classmethod
    def get_default_config(cls, name, description):
        return {
            'jsbox_app_config': {
                'config': {
                    'key': 'config',
                    'value': json.dumps({'name': slugify(name)})
                }
            }
        }

    def configured_endpoints(self, config):
        try:
            js_config = jsbox_js_config(config)
        except Exception:
            return []

        # vumi-jssandbox-toolkit v2 endpoints
        try:
            v2_endpoints = list(js_config["endpoints"].keys())
        except Exception:
            v2_endpoints = []
        # vumi-jssandbox-toolkit v1 endpoints
        try:
            pool, tag = js_config["sms_tag"]
            v1_endpoints = [u"%s:%s" % (pool, tag)]
        except Exception:
            v1_endpoints = []

        endpoints = v1_endpoints + v2_endpoints
        endpoints = [ep for ep in endpoints if isinstance(ep, unicode)]
        return sorted(set(endpoints))
