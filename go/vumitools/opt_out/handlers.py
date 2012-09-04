# -*- test-case-name: go.vumitools.tests.test_opt_out -*-

from twisted.internet.defer import inlineCallbacks

from vumi import log

from go.vumitools.handler import EventHandler


class OptInHandler(EventHandler):

    @inlineCallbacks
    def handle_event(self, event, handler_config):
        """Set the appropriate opt-in/out flags on a contact objects.

        The event should have the following fields:

         * ``campaign_name``: Name of the campaign to opt into/out of.

         * ``operation``: Must be ``opt_in`` or ``opt_out``.

         * ``contact_id``: Contact id to operate on. (optional)

        An Example of a event_dispatcher.yaml config file, with mapped
        conversations in the config:

            transport_name: event_dispatcher
            event_handlers:
                opt_in_handler: go.vumitools.opt_out.handlers.OptInHandler
            account_handler_configs:
                '73ad76ec8c2e40858dc9d6b934049d95':
                - - ['a6a20571e77f4aa89a8b10a771b005bc', opt_in]
                  - - [opt_in_handler, {}]
        """

        log.info(
            "OptInHandler handling event: %s with config: %s" % (
            event, handler_config))
        user_api = self.get_user_api(event.payload['account_key'])
        fields = event.payload['content']

        contact = yield user_api.contact_store.get_contact_by_key(
            fields['contact_id'])
        contact.optin[fields['campaign_name']] = {
            'opt_in': u'opted_in',
            'opt_out': u'opted_out',
            }[fields['operation']]
        yield contact.save()
