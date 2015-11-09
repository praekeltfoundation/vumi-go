# -*- test-case-name: go.apps.subscription.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from go.vumitools.app_worker import GoApplicationWorker


class SubscriptionApplication(GoApplicationWorker):
    """
    Application that recognises keywords and fires events.
    """
    worker_name = 'subscription_application'

    def handlers_for_content(self, conv, content):
        words = (content or '').strip().split() + ['']
        keyword = words[0].lower()
        handlers = conv.get_config().get('handlers', [])
        return [handler for handler in handlers
                if handler['keyword'].lower() == keyword]

    @inlineCallbacks
    def consume_user_message(self, message):
        msg_mdh = self.get_metadata_helper(message)
        user_api = self.get_user_api(msg_mdh.get_account_key())
        conv = yield msg_mdh.get_conversation()

        delivery_class = user_api.delivery_class_for_msg(message)
        contact = yield user_api.contact_store.contact_for_addr(
            delivery_class, message['from_addr'], create=True)
        # We're guaranteed to have a contact here, because we create one if we
        # can't find an existing one.

        handlers = self.handlers_for_content(conv, message['content'])
        if not handlers:
            yield self.reply_to(message, "Unrecognised keyword.")
            return

        for handler in handlers:
            status = {
                'subscribe': u'subscribed',
                'unsubscribe': u'unsubscribed',
                }[handler['operation']]
            contact.subscription[handler['campaign_name']] = status
            yield contact.save()
            if handler['reply_copy']:
                yield self.reply_to(message, handler['reply_copy'])
