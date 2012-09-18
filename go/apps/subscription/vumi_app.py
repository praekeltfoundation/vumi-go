# -*- test-case-name: go.apps.subscription.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from vumi.middleware.tagger import TaggingMiddleware
from vumi import log

from go.vumitools.app_worker import GoApplicationWorker


class SubscriptionApplication(GoApplicationWorker):
    """
    Application that recognises keywords and fires events.
    """
    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'subscription_application'

    @inlineCallbacks
    def send_message(self, batch_id, to_addr, content, msg_options):
        # TODO: Update
        msg = yield self.send_to(to_addr, content, **msg_options)
        yield self.vumi_api.mdb.add_outbound_message(msg, batch_id=batch_id)
        log.info('Stored outbound %s' % (msg,))

    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):
        if not is_client_initiated:
            log.warning('Trying to start a server initiated conversation '
                        'on a subscription handler.')

    def handlers_for_content(self, conv, content):
        keyword = content.strip().split()[0].lower()
        handlers = conv.get_metadata(default={}).get('handlers', [])
        return [handler for handler in handlers
                if handler['keyword'].lower() == keyword]

    @inlineCallbacks
    def consume_user_message(self, message):
        gmd = self.get_go_metadata(message)
        user_api = self.get_user_api((yield gmd.get_account_key()))
        conv = user_api.wrap_conversation((yield gmd.get_conversation()))

        contact = yield user_api.contact_store.contact_for_addr(
            conv.delivery_class, message['from_addr'])
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

    def consume_ack(self, event):
        return self.vumi_api.mdb.add_event(event)

    def consume_delivery_report(self, event):
        return self.vumi_api.mdb.add_event(event)

    @inlineCallbacks
    def process_command_send_message(self, *args, **kwargs):
        # TODO: Update
        command_data = kwargs['command_data']
        log.info('Processing send_message: %s' % kwargs)
        yield self.send_message(
                command_data['batch_id'],
                command_data['to_addr'],
                command_data['content'],
                command_data['msg_options'])
