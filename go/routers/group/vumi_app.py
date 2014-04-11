# -*- test-case-name: go.routers.group.tests.test_vumi_app -*-

from django.conf import settings

from twisted.internet.defer import inlineCallbacks

from vumi import log
from vumi.config import ConfigList

from go.vumitools.app_worker import GoRouterWorker
from go.vumitools.contact import ContactError, ContactNotFoundError
from go.vumitools.api import VumiUserApi


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
        contact_groups = set(contact.groups.keys())
        rules = dict([(x['group'], x['endpoint']) for x in config.rules])
        for group_key in contact_groups:
            if group_key not in rules:
                continue
            return rules[group_key]
        return 'default'

    @inlineCallbacks
    def handle_inbound(self, config, msg, conn_name):
        log.msg("Handling inbound: %s" % (msg,))

        user_account = config.router.user_account
        api = yield VumiUserApi.from_config_async(
            user_account.key, settings.VUMI_API_CONFIG)
        contact_store = api.contact_store
        addr = msg['from_addr']
        dclass = api.delivery_class_for_msg(msg)

        try:
            contact = yield contact_store.contact_for_addr(
                dclass,
                addr,
                create=False
            )
        except ContactNotFoundError:
            yield self.publish_inbound(msg, 'default')
        except ContactError:
            log.err()
        else:
            endpoint = self.endpoint_for_contact(config, contact)
            yield self.publish_inbound(msg, endpoint)

    def handle_outbound(self, config, msg, conn_name):
        log.msg("Handling outbound: %s" % (msg,))
        return self.publish_outbound(msg, 'default')
