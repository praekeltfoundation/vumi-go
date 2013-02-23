from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportEvent
from vumi.endpoint_dispatchers import RoutingTableDispatcher

from go.app_worker import GoWorkerMixin, GoWorkerConfigMixin


class AccountRoutingTableDispatcherConfig(RoutingTableDispatcher.CONFIG_CLASS,
                                          GoWorkerConfigMixin):
    pass


class AccountRoutingTableDispatcher(RoutingTableDispatcher, GoWorkerMixin):
    CONFIG_CLASS = AccountRoutingTableDispatcherConfig

    def setup_dispatcher(self):
        # This assumes RoutingTableDispatcher.setup_dispatcher() is empty.
        return self._go_setup_worker()

    def teardown_dispatcher(self):
        # This assumes RoutingTableDispatcher.teardown_dispatcher() is empty.
        return self._go_teardown_worker()

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
