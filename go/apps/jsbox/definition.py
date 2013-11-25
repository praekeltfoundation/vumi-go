import json

from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class ViewLogsAction(ConversationAction):
    action_name = 'view_logs'
    action_display_name = 'View Sandbox Logs'
    redirect_to = 'jsbox_logs'


class ExportAnswersAction(ConversationAction):
    action_name = 'export_answers'
    action_display_name = 'Export answers to CSV'
    redirect_to = 'jsbox_answers'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'jsbox'
    conversation_display_name = 'Javascript App'

    actions = (ViewLogsAction, ExportAnswersAction)

    def configured_endpoints(self, config):
        # TODO: make jsbox apps define these explicitly and
        #       update the outbound resource to check and
        #       complain if a jsbox app sends on an endpoint
        #       it hasn't defined.
        app_config = config.get("jsbox_app_config", {})
        raw_js_config = app_config.get("config", {}).get("value", {})
        try:
            js_config = json.loads(raw_js_config)
            pool, tag = js_config.get("sms_tag")
        except Exception:
            return []
        return ["%s:%s" % (pool, tag)]
