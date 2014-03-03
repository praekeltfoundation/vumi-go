import json

from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class ViewLogsAction(ConversationAction):
    action_name = 'view_logs'
    action_display_name = 'View Sandbox Logs'
    redirect_to = 'jsbox_logs'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'jsbox'
    conversation_display_name = 'Javascript App'

    actions = (ViewLogsAction,)

    def configured_endpoints(self, config):
        app_config = config.get("jsbox_app_config", {})
        raw_js_config = app_config.get("config", {}).get("value", {})
        try:
            js_config = json.loads(raw_js_config)
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
