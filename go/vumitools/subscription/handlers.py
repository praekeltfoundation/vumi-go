# -*- test-case-name: go.vumitools.subscription.tests.test_handlers -*-

from twisted.internet.defer import inlineCallbacks

from vumi import log

from go.vumitools.handler import EventHandler


class SubscriptionHandler(EventHandler):

    @inlineCallbacks
    def handle_event(self, event, handler_config):
        """Set the appropriate subscription flag on a contact object.

        The event should have the following fields:

         * ``campaign_name``: Name of the campaign to manage subscription to.

         * ``operation``: Must be ``subscribe`` or ``unsubscribe``.

         * ``contact_id``: Contact id to operate on.

        An Example of a event_dispatcher.yaml config file, with mapped
        conversations in the config:

            transport_name: event_dispatcher
            event_handlers:
                subscription_handler:
                    go.vumitools.subscription.handlers.SubscriptionHandler
            account_handler_configs:
                '73ad76ec8c2e40858dc9d6b934049d95':
                - - ['a6a20571e77f4aa89a8b10a771b005bc', subscribe]
                  - - [subscription_handler, {}]
        """

        log.info(
            "SubscriptionHandler handling event: %s with config: %s" % (
                event, handler_config))
        user_api = self.get_user_api(event.payload['account_key'])
        fields = event.payload['content']

        contact = yield user_api.contact_store.get_contact_by_key(
            fields['contact_id'])
        contact.subscription[fields['campaign_name']] = {
            'subscribe': u'subscribed',
            'unsubscribe': u'unsubscribed',
            }[fields['operation']]
        yield contact.save()
