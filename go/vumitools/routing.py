# -*- test-case-name: go.vumitools.tests.test_routing -*-

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportEvent
from vumi.dispatchers.endpoint_dispatchers import RoutingTableDispatcher
from vumi.middleware.base import BaseMiddleware
from vumi.connectors import ReceiveInboundConnector, ReceiveOutboundConnector

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

    def setup_middleware(self):
        """Create middlewares from config."""
        d = super(AccountRoutingTableDispatcher, self).setup_middleware()
        mw = AccountRoutingTableDispatcherMiddleware(
            'account_routing_table', {}, self)
        d.addCallback(lambda _: mw.setup_middleware())
        d.addCallback(lambda _: self.middlewares.append(mw))
        return d

    @inlineCallbacks
    def get_message_config(self, msg):
        if isinstance(msg, TransportEvent):
            msg = yield self.find_message_for_event(msg)

        metadata = self.get_go_metadata(msg)
        user_account_key = yield metadata.get_account_key()
        user_api = self.get_user_api(user_account_key)
        routing_table = yield user_api.get_routing_table()
        config_dict = self.config.copy()
        config_dict['routing_table'] = routing_table
        returnValue(self.CONFIG_CLASS(config_dict))


class AccountRoutingTableDispatcherMiddleware(BaseMiddleware):

    def _guess_connector_type(self, connector_name):
        conn = self.worker.connectors[connector_name]
        if isinstance(conn, ReceiveInboundConnector):
            return 'receive_inbound'
        elif isinstance(conn, ReceiveOutboundConnector):
            return 'receive_outbound'
        else:
            return 'unknown'

    def handle_inbound(self, message, connector_name):
        conn_type = self._guess_connector_type(connector_name)
        if conn_type == 'receive_inbound':
            return self.handle_consume_inbound(message, connector_name)
        elif conn_type == 'receive_outbound':
            return self.handle_publish_inbound(message, connector_name)
        else:
            raise RuntimeError("Unknown connector type: %s" % (conn_type,))

    def handle_outbound(self, message, connector_name):
        conn_type = self._guess_connector_type(connector_name)
        if conn_type == 'receive_inbound':
            return self.handle_publish_outbound(message, connector_name)
        elif conn_type == 'receive_outbound':
            return self.handle_consume_outbound(message, connector_name)
        else:
            raise RuntimeError("Unknown connector type: %s" % (conn_type,))

    def handle_event(self, message, connector_name):
        conn_type = self._guess_connector_type(connector_name)
        if conn_type == 'receive_inbound':
            return self.handle_consume_event(message, connector_name)
        elif conn_type == 'receive_outbound':
            return self.handle_publish_event(message, connector_name)
        else:
            raise RuntimeError("Unknown connector type: %s" % (conn_type,))

    def handle_consume_inbound(self, message, connector_name):
        tag = message.get('helper_metadata', {}).get('tag', {}).get('tag')
        if tag is not None:
            endpoint = message.get_routing_endpoint()
            message.set_routing_endpoint(
                "%s:%s:%s" % (tag[0], tag[1], endpoint))
        return message

    def handle_publish_inbound(self, message, connector_name):
        conv_key, endpoint = message.get_routing_endpoint().split(':', 1)
        go_metadata = message['helper_metadata'].setdefault('go', {})
        go_metadata['conversation_key'] = conv_key
        # XXX: We should either guarantee the following or not rely on it being
        #      set in GoMessageMetadata.
        go_metadata['conversation_type'] = connector_name
        message.set_routing_endpoint(endpoint)
        return message

    def handle_consume_outbound(self, message, connector_name):
        # TODO: Clean up GoMessageMetadata and put some of this logic there.
        go_metadata = message.get('helper_metadata', {}).get('go', {})
        conv_key = go_metadata.get('conversation_key')
        if conv_key is not None:
            endpoint = message.get_routing_endpoint()
            message.set_routing_endpoint("%s:%s" % (conv_key, endpoint))
        return message

    def handle_publish_outbound(self, message, connector_name):
        tag0, tag1, endpoint = message.get_routing_endpoint().split(':', 2)
        message.set_routing_endpoint(endpoint)
        message['helper_metadata'].setdefault('tag', {})['tag'] = [tag0, tag1]
        return message

    def handle_consume_event(self, message, connector_name):
        raise NotImplementedError()
        tag = message.get('helper_metadata', {}).get('tag', {}).get('tag')
        if tag is not None:
            endpoint = message.get_routing_endpoint()
            message.set_routing_endpoint(
                "%s:%s:%s" % (tag[0], tag[1], endpoint))
        return message

    def handle_publish_event(self, message, connector_name):
        raise NotImplementedError()
        conv_key, endpoint = message.get_routing_endpoint().split(':', 1)
        go_metadata = message['helper_metadata'].setdefault('go', {})
        go_metadata['conversation_key'] = conv_key
        # XXX: We should either guarantee the following or not rely on it being
        #      set in GoMessageMetadata.
        go_metadata['conversation_type'] = connector_name
        message.set_routing_endpoint(endpoint)
        return message
