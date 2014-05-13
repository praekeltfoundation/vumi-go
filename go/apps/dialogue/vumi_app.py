# -*- test-case-name: go.apps.dialogue.tests.test_vumi_app -*-

import pkg_resources
import json
import logging

from vumi.application.sandbox import SandboxResource
from twisted.internet.defer import inlineCallbacks

from go.apps.jsbox.vumi_app import JsBoxConfig, JsBoxApplication


class PollConfigResource(SandboxResource):
    """Resource that provides access to dialogue conversation config."""

    def _get_config(self, conversation):
        """Returns a virtual sandbox config for the given dialogue.

        :returns:
            JSON string containg the configuration dictionary.
        """

        config = {
            "name": "poll-%s" % conversation.key
        }

        poll = conversation.config.get("poll", {})
        poll_metadata = poll.get('poll_metadata', {})
        delivery_class = poll_metadata.get('delivery_class')

        if delivery_class is not None:
            config['delivery_class'] = delivery_class

        return json.dumps(config)

    def _get_poll(self, conversation):
        """Returns the poll definition from the given dialogue.

        :returns:
            JSON string containing the poll definition.
        """
        poll = conversation.config.get("poll")
        return poll

    def handle_get(self, api, command):
        key = command.get("key")
        if key is None:
            return self.reply(command, success=False)
        conversation = self.app_worker.conversation_for_api(api)
        if key == "config":
            value = self._get_config(conversation)
        elif key == "poll":
            value = self._get_poll(conversation)
        else:
            # matches what is returned for unknown keys by
            # go.apps.jsbox.vumi_app.ConversationConfigResource
            value = {}
        return self.reply(command, value=value, success=True)


class DialogueConfig(JsBoxConfig):

    _cached_javascript = None

    @property
    def javascript(self):
        if self._cached_javascript is None:
            self._cached_javascript = pkg_resources.resource_string(
                "go.apps.dialogue", "vumi_app.js")
        return self._cached_javascript


class DialogueApplication(JsBoxApplication):
    CONFIG_CLASS = DialogueConfig

    worker_name = 'dialogue_application'
