# -*- test-case-name: go.apps.sna.test_handlers -*-
from twisted.internet.defer import inlineCallbacks

from go.vumitools.opt_out import OptOutStore
from go.vumitools.contact import ContactStore
from go.vumitools.handler import EventHandler

from vumi import log

from vxpolls.manager import PollManager


class USSDOptOutHandler(EventHandler):

    def setup_handler(self):
        self.pm_prefix = self.config['poll_manager_prefix']
        self.vumi_api = self.dispatcher.vumi_api
        self.pm = PollManager(self.vumi_api.redis, self.pm_prefix)

    def teardown_handler(self):
        self.pm.stop()

    @inlineCallbacks
    def handle_event(self, event, handler_config):
        """

        Expects the event 'content' to be a dict with the following keys
        and values:

        NOTE:   perhaps all we need here is the message_id and lookup the
                rest of the required data from the message in the message store

        :param from_addr:
            the from_addr of the user interaction that triggered the event
        :param message_id:
            the id of the message that triggered the event, used to keep an
            audit trail of opt-outs and which messages they were triggered by.
        :param transport_type:
            the transport_type that the message was received on.

        """
        account_key = event.payload['account_key']
        oo_store = OptOutStore(self.vumi_api.manager, account_key)
        contact_store = ContactStore(self.vumi_api.manager, account_key)

        event_data = event.payload['content']

        from_addr = event_data['from_addr']
        message_id = event_data['message_id']
        transport_type = event_data.get('transport_type')

        if transport_type != 'ussd':
            log.info("SNAUSSDOptOutHandler skipping non-ussd"
                     " message for %r" % (from_addr,))
            return
        contact = yield contact_store.contact_for_addr('ussd', from_addr)
        if contact:
            opted_out = contact.extra['opted_out']
            if opted_out is not None and opted_out.isdigit():
                if int(opted_out) > 1:
                    yield oo_store.new_opt_out('msisdn', from_addr, {
                        'message_id': message_id,
                    })
                else:
                    yield oo_store.delete_opt_out('msisdn', from_addr)
