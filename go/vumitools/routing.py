# -*- test-case-name: go.vumitools.tests.test_routing -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.dispatchers.endpoint_dispatchers import RoutingTableDispatcher
from vumi import log

from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin


class AccountRoutingTableDispatcherConfig(RoutingTableDispatcher.CONFIG_CLASS,
                                          GoWorkerConfigMixin):
    pass


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
    def get_message_config(self, msg):
        metadata = self.get_go_metadata(msg)
        user_account_key = yield metadata.get_account_key()
        user_api = self.get_user_api(user_account_key)
        routing_table = yield user_api.get_routing_table()
        config_dict = self.config.copy()
        config_dict['routing_table'] = routing_table
        returnValue(self.CONFIG_CLASS(config_dict))

    def set_tag_endpoint(self, msg):
        tag = msg.get('helper_metadata', {}).get('tag', {}).get('tag')
        if tag is not None:
            endpoint = msg.get_routing_endpoint()
            msg.set_routing_endpoint("%s:%s:%s" % (tag[0], tag[1], endpoint))
        else:
            log.warning("No tag for inbound message: %s" % (msg,))
        return msg

    def set_conversation_endpoint(self, msg):
        # TODO: Clean up GoMessageMetadata and put some of this logic there.
        go_metadata = msg.get('helper_metadata', {}).get('go', {})
        conv_key = go_metadata.get('conversation_key')
        if conv_key is not None:
            endpoint = msg.get_routing_endpoint()
            msg.set_routing_endpoint("%s:%s" % (conv_key, endpoint))
        else:
            log.warning("No conversation for outbound message: %s" % (msg,))
        return msg

    def set_tag_metadata(self, msg, target):
        _connector_name, endpoint = target
        tag0, tag1, endpoint = endpoint.split(':', 2)
        msg['helper_metadata'].setdefault('tag', {})['tag'] = [tag0, tag1]
        msg.set_routing_endpoint(endpoint)
        return msg

    def set_conversation_metadata(self, msg, target):
        connector_name, endpoint = target
        conv_key, endpoint = endpoint.split(':', 1)
        go_metadata = msg['helper_metadata'].setdefault('go', {})
        go_metadata['conversation_key'] = conv_key
        # XXX: We should either guarantee the following or not rely on it being
        #      set in GoMsgMetadata.
        go_metadata['conversation_type'] = connector_name
        msg.set_routing_endpoint(endpoint)
        return msg

    def process_inbound(self, config, msg, connector_name):
        self.set_tag_endpoint(msg)
        target = self.find_target(config, msg, connector_name)
        if target is None:
            return
        self.set_conversation_metadata(msg, target)
        return self.publish_inbound(msg, target[0], None)

    def process_outbound(self, config, msg, connector_name):
        self.set_conversation_endpoint(msg)
        target = self.find_target(config, msg, connector_name)
        if target is None:
            return
        self.set_tag_metadata(msg, target)
        return self.publish_outbound(msg, target[0], None)

    @inlineCallbacks
    def process_event(self, config, event, connector_name):
        msg = yield self.find_message_for_event(event)
        go_metadata = msg.get('helper_metadata', {}).get('go', {})
        conv_type = go_metadata.get('conversation_type')
        conv_key = go_metadata.get('conversation_key')
        if conv_type and conv_key:
            yield self.publish_event(event, conv_type, "default")
        else:
            log.warning("No conversation for message for event: %s" % (event,))
