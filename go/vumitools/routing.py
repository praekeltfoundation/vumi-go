# -*- test-case-name: go.vumitools.tests.test_routing -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.dispatchers.endpoint_dispatchers import RoutingTableDispatcher
from vumi.config import ConfigList, ConfigDict, ConfigText
from vumi.message import TransportEvent
from vumi import log

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin


class AccountRoutingTableDispatcherConfig(RoutingTableDispatcher.CONFIG_CLASS,
                                          GoWorkerConfigMixin):
    application_connector_mapping = ConfigDict(
        "Mapping from conversation_type to connector name.", static=True)
    message_tag = ConfigList("Tag for the message, if any.")
    tagpool_metadata = ConfigDict(
        "Tagpool metadata for the tag attached to the message if any.")
    conversation_info = ConfigDict(
        "Conversation info for the tag attached to the message if any.")
    user_account_key = ConfigText("UserAccount key.")


class AccountRoutingTableDispatcher(RoutingTableDispatcher, GoWorkerMixin):
    CONFIG_CLASS = AccountRoutingTableDispatcherConfig
    worker_name = 'account_routing_table_dispatcher'

    def setup_dispatcher(self):
        # This assumes RoutingTableDispatcher.setup_dispatcher() is empty.
        return self._go_setup_worker()

    def teardown_dispatcher(self):
        # This assumes RoutingTableDispatcher.teardown_dispatcher() is empty.
        return self._go_teardown_worker()

    @inlineCallbacks
    def get_config(self, msg):
        if isinstance(msg, TransportEvent):
            msg = yield self.find_message_for_event(msg)

        config_dict = self.config.copy()
        user_account_key = None

        # TODO: Better way to look up account for either tag or conversation.
        tag = msg.get('helper_metadata', {}).get('tag', {}).get('tag')
        if tag is not None:
            tagpool_md = yield self.vumi_api.tpm.get_metadata(tag[0])
            config_dict['tagpool_metadata'] = tagpool_md
            config_dict['message_tag'] = tag
            tag_info = yield self.vumi_api.mdb.get_tag_info(tuple(tag))
            user_account_key = tag_info.metadata['user_account']

        msg_mdh = self.get_metadata_helper(msg)
        if user_account_key is None:
            user_account_key = yield msg_mdh.get_account_key()

        user_api = self.get_user_api(user_account_key)
        routing_table = yield user_api.get_routing_table()
        config_dict['routing_table'] = routing_table

        config_dict['conversation_info'] = msg_mdh.get_conversation_info()
        config_dict['user_account_key'] = user_account_key.decode('utf-8')

        returnValue(self.CONFIG_CLASS(config_dict))

    def get_application_connector(self, conversation_type):
        mapping = self.get_static_config().application_connector_mapping or {}
        return mapping.get(conversation_type, conversation_type)

    def process_inbound(self, config, msg, connector_name):
        log.debug("Processing inbound: %s" % (msg,))
        if not config.message_tag:
            log.warning("No tag found for inbound message: %s" % (msg,))
            return

        target = self.find_target(config, msg, ':'.join(config.message_tag))
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        target_conn, endpoint = target
        conv_type, conv_key = target_conn.split(':', 1)
        go_metadata = msg.get('helper_metadata', {}).setdefault('go', {})
        go_metadata['conversation_type'] = conv_type
        go_metadata['conversation_key'] = conv_key
        go_metadata['user_account'] = config.user_account_key

        conv_connector = self.get_application_connector(conv_type)
        return self.publish_inbound(msg, conv_connector, endpoint)

    def process_outbound(self, config, msg, connector_name):
        log.debug("Processing outbound: %s" % (msg,))
        if not config.conversation_info:
            log.warning(
                "No conversation info found for outbound message: %s" % (msg,))
            return

        conv_conn = ':'.join([config.conversation_info['conversation_type'],
                              config.conversation_info['conversation_key']])
        target = self.find_target(config, msg, conv_conn)
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        target_conn, endpoint = target
        tag = target_conn.split(':', 1)
        msg['helper_metadata'].setdefault('tag', {})['tag'] = tag

        def publish_cb(tagpool_metadata):
            transport_name = tagpool_metadata.get('transport_name')
            if transport_name is None:
                log.warning("No transport_name for tag: (%r, %r)" % tag)
                return

            return self.publish_outbound(msg, transport_name, endpoint)

        d = self.vumi_api.tpm.get_metadata(tag[0])
        d.addCallback(publish_cb)
        return d

    def process_event(self, config, event, connector_name):
        log.debug("Processing event: %s" % (event,))
        if not config.conversation_info:
            log.warning("No conversation info found on outbound message "
                        "for event: %s" % (event,))
            return
        conv_type = config.conversation_info['conversation_type']
        conv_connector = self.get_application_connector(conv_type)
        return self.publish_event(event, conv_connector, "default")
