# -*- test-case-name: go.routers.keyword.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

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

    def lookup_target(self, config, msg):
        first_word = ((msg['content'] or '').strip().split() + [''])[0]
        for keyword, target in config.keyword_endpoint_mapping.iteritems():
            if keyword.lower() == first_word.lower():
                return target
        return 'default'

    def handle_inbound(self, config, msg, conn_name):
        log.debug("Handling inbound: %s" % (msg,))
        return self.publish_inbound(msg, self.lookup_target(config, msg))

    def handle_outbound(self, config, msg, conn_name):
        log.debug("Handling outbound: %s" % (msg,))
        return self.publish_outbound(msg, 'default')
