# -*- test-case-name: go.routers.group.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks

from vumi import log
from vumi.config import ConfigList

from go.vumitools.app_worker import GoRouterWorker
from go.vumitools.contact import ContactError, ContactNotFoundError


class GroupRouterConfig(GoRouterWorker.CONFIG_CLASS):
    rules = ConfigList(
        "List of groups and endpoint pairs",
        default=[])


class GroupRouter(GoRouterWorker):
    """
    Router that splits inbound messages based on contact group membership
    """
    CONFIG_CLASS = GroupRouterConfig

    worker_name = 'group_router'

    def endpoint_for_contact(self, config, contact):
        if contact is None:
            return 'default'
        contact_groups = set(contact.groups.keys())
        for rule in config.rules:
            if rule['group'] in contact_groups:
                return rule['endpoint']
        return 'default'

    @inlineCallbacks
    def handle_inbound(self, config, msg, conn_name):
        log.msg("Handling inbound: %s" % (msg,))

        try:
            contact = yield self.get_contact_for_message(msg, create=False)
        except ContactNotFoundError:
            contact = None
        except ContactError:
            log.err()
            return

        endpoint = self.endpoint_for_contact(config, contact)
        yield self.publish_inbound(msg, endpoint)

    def handle_outbound(self, config, msg, conn_name):
        log.msg("Handling outbound: %s" % (msg,))
        return self.publish_outbound(msg, 'default')
