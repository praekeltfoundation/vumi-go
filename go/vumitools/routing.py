# -*- test-case-name: go.vumitools.tests.test_routing -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.dispatchers.endpoint_dispatchers import RoutingTableDispatcher
from vumi.config import ConfigList, ConfigDict, ConfigText
from vumi.message import TransportEvent
from vumi import log

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin
from go.vumitools.middleware import OptOutMiddleware
from go.vumitools.account import GoConnector


class AccountRoutingTableDispatcherConfig(RoutingTableDispatcher.CONFIG_CLASS,
                                          GoWorkerConfigMixin):
    application_connector_mapping = ConfigDict(
        "Mapping from conversation_type to connector name.", static=True)
    opt_out_connector = ConfigText(
        "Connector to publish opt-out messages on.", static=True)
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

        msg_mdh = self.get_metadata_helper(msg)

        # TODO: Better way to look up account for either tag or conversation.
        if msg_mdh.tag is not None:
            tagpool_md = yield self.vumi_api.tpm.get_metadata(msg_mdh.tag[0])
            config_dict['tagpool_metadata'] = tagpool_md
            config_dict['message_tag'] = msg_mdh.tag
            tag_info = yield self.vumi_api.mdb.get_tag_info(tuple(msg_mdh.tag))
            user_account_key = tag_info.metadata['user_account']

        if user_account_key is None:
            user_account_key = msg_mdh.get_account_key()

        user_api = self.get_user_api(user_account_key)
        routing_table = yield user_api.get_routing_table()
        config_dict['routing_table'] = routing_table

        config_dict['conversation_info'] = msg_mdh.get_conversation_info()
        config_dict['user_account_key'] = user_account_key.decode('utf-8')

        returnValue(self.CONFIG_CLASS(config_dict))

    def get_application_connector(self, conversation_type):
        mapping = self.get_static_config().application_connector_mapping or {}
        return mapping.get(conversation_type, conversation_type)

    def handle_opt_out(self, msg):
        return self.publish_inbound(
            msg, self.get_static_config().opt_out_connector, 'default')

    def process_inbound(self, config, msg, connector_name):
        log.debug("Processing inbound: %s" % (msg,))
        if not config.message_tag:
            log.warning("No tag found for inbound message: %s" % (msg,))
            return

        msg_mdh = self.get_metadata_helper(msg)
        msg_mdh.set_user_account(config.user_account_key)

        if OptOutMiddleware.is_optout_message(msg):
            return self.handle_opt_out(msg)

        src_conn = str(GoConnector.for_transport_tag(config.message_tag[0],
                                                     config.message_tag[1]))
        target = self.find_target(config, msg, src_conn)
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        conn = GoConnector.parse(target[0])
        assert conn.ctype == conn.CONVERSATION
        msg_mdh.set_conversation_info(conn.conv_type, conn.conv_key)

        conv_connector = self.get_application_connector(conn.conv_type)
        return self.publish_inbound(msg, conv_connector, target[1])

    def process_outbound(self, config, msg, connector_name):
        log.debug("Processing outbound: %s" % (msg,))
        if not config.conversation_info:
            log.warning(
                "No conversation info found for outbound message: %s" % (msg,))
            return

        conv_conn = str(GoConnector.for_conversation(
            config.conversation_info['conversation_type'],
            config.conversation_info['conversation_key']))
        target = self.find_target(config, msg, conv_conn)
        if target is None:
            log.debug("No target found for message from '%s': %s" % (
                connector_name, msg))
            return

        conn = GoConnector.parse(target[0])
        assert conn.ctype == conn.TRANSPORT_TAG
        tag = [conn.tagpool, conn.tagname]
        msg['helper_metadata'].setdefault('tag', {})['tag'] = tag

        def publish_cb(tagpool_metadata):
            transport_name = tagpool_metadata.get('transport_name')
            if transport_name is None:
                log.warning("No transport_name for tag: (%r, %r)" % tag)
                return

            return self.publish_outbound(msg, transport_name, target[1])

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
