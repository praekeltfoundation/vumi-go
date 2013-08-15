# -*- test-case-name: go.apps.static_reply.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from vumi.config import ConfigText

from go.vumitools.app_worker import GoApplicationWorker


class StaticReplyConfig(GoApplicationWorker.CONFIG_CLASS):
    reply_text = ConfigText(
        "Reply text to send in response to inbound messages.")


class StaticReplyApplication(GoApplicationWorker):
    """
    Application that replies to incoming messages with a configured response.
    """
    worker_name = 'static_reply_application'
    CONFIG_CLASS = StaticReplyConfig

    @inlineCallbacks
    def consume_user_message(self, message):
        config = yield self.get_message_config(message)
        if config.reply_text:
            yield self.reply_to(
                message, config.reply_text, continue_session=False)
