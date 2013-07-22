# -*- test-case-name: go.routers.keyword.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

import re

from twisted.internet.defer import inlineCallbacks

from vumi import log
from vumi.config import ConfigDict

from go.vumitools.app_worker import GoRouterWorker


class KeywordRouterConfig(GoRouterWorker.CONFIG_CLASS):
    keyword_endpoint_mapping = ConfigDict(
        "Mapping from case-insensitive keyword regex to endpoint name.",
        default={})


class KeywordRouter(GoRouterWorker):
    """
    Router that splits inbound messages based on keywords.
    """
    CONFIG_CLASS = KeywordRouterConfig

    worker_name = 'keyword_router'

    def get_config(self, msg):
        return self.get_message_config(msg)

    def lookup_target(self, config, msg):
        first_word = ((msg['content'] or '').strip().split() + [''])[0]
        for keyword_re, target in config.keyword_endpoint_mapping.iteritems():
            if re.match(keyword_re, first_word, re.IGNORECASE):
                return target
        return 'default'

    @inlineCallbacks
    def handle_event(self, config, event, conn_name):
        log.debug("Handling event: %s" % (event,))
        message = yield self.find_message_for_event(event)
        if message is None:
            log.error('Unable to find message for %s, user_message_id: %s' % (
                event['event_type'], event.get('user_message_id')))
            return
        # TODO: handle the event.

    def handle_inbound(self, config, msg, conn_name):
        log.debug("Handling inbound: %s" % (msg,))
        return self.publish_inbound(msg, self.lookup_target(config, msg))

    def handle_outbound(self, config, msg, conn_name):
        log.debug("Handling outbound: %s" % (msg,))
        return self.publish_outbound(msg, 'default')
