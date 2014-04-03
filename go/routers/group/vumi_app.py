# -*- test-case-name: go.routers.group.tests.test_vumi_app -*-

from django.conf import settings

from twisted.internet.defer import inlineCallbacks

from vumi import log
from vumi.config import ConfigList

from go.vumitools.app_worker import GoRouterWorker
from go.vumitools.contact import ContactNotFoundError
from go.vumitools.api import VumiUserApi


class GroupRouterConfig(GoRouterWorker.CONFIG_CLASS):
    groups = ConfigList(
        "Contact groups to test user membership",
        default=[])


class GroupRouter(GoRouterWorker):
    """
    Router that splits inbound messages based on contact group membership
    """
    CONFIG_CLASS = GroupRouterConfig

    worker_name = 'group_router'

    @inlineCallbacks
    def handle_inbound(self, config, msg, conn_name):
        log.debug("Handling inbound: %s" % (msg,))

        user_account = config.router.user_account
        api = yield VumiUserApi.from_config_async(
            user_account.key, settings.VUMI_API_CONFIG)
        contact_store = api.contact_store
        addr = msg['from_addr']
        delivery_class = api.delivery_class_for_msg(msg)

        try:
            contact = yield contact_store.contact_for_addr(delivery_class,
                                                           addr)
        except ContactNotFoundError:
            yield self.publish_inbound(msg, 'default')
        else:
            user_groups = set(contact.groups.keys())
            magic_groups = set(config.groups)
            if user_groups.isdisjoint(magic_groups):
                yield self.publish_inbound(msg, 'default')
            else:
                yield self.publish_inbound(msg, 'selected')

    def handle_outbound(self, config, msg, conn_name):
        log.debug("Handling outbound: %s" % (msg,))
        return self.publish_outbound(msg, 'default')
