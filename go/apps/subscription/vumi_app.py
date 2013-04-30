# -*- test-case-name: go.apps.subscription.tests.test_vumi_app -*-
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from vumi import log

from go.vumitools.app_worker import GoApplicationWorker


class SubscriptionApplication(GoApplicationWorker):
    """
    Application that recognises keywords and fires events.
    """
    worker_name = 'subscription_application'

    @inlineCallbacks
    def send_message(self, batch_id, to_addr, content, msg_options):
        # TODO: Update
        msg = yield self.send_to(
            to_addr, content, endpoint='default', **msg_options)
        yield self.vumi_api.mdb.add_outbound_message(msg, batch_id=batch_id)
        log.info('Stored outbound %s' % (msg,))

    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):
        if not is_client_initiated:
            log.warning('Trying to start a server initiated conversation '
                        'on a subscription handler.')

    def handlers_for_content(self, conv, content):
        words = (content or '').strip().split() + ['']
        keyword = words[0].lower()
        handlers = conv.get_metadata(default={}).get('handlers', [])
        return [handler for handler in handlers
                if handler['keyword'].lower() == keyword]

    @inlineCallbacks
    def consume_user_message(self, message):
        msg_mdh = self.get_metadata_helper(message)
        user_api = self.get_user_api(msg_mdh.get_account_key())
        conv = yield msg_mdh.get_conversation()

        contact = yield user_api.contact_store.contact_for_addr(
            conv.delivery_class, message['from_addr'], create=True)
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

    @inlineCallbacks
    def collect_metrics(self, user_api, conversation_key):
        conv = yield user_api.get_wrapped_conversation(conversation_key)
        contact_proxy = user_api.contact_store.contacts

        campaign_names = set()
        for handler in conv.get_metadata(default={}).get('handlers', []):
            campaign_names.add(handler['campaign_name'])

        for campaign_name in campaign_names:
            self.publish_conversation_metric(
                conv, '.'.join([campaign_name, "subscribed"]),
                (yield contact_proxy.raw_search(
                    "subscription-%s:subscribed" % (
                        campaign_name,)).get_count()))
            self.publish_conversation_metric(
                conv, '.'.join([campaign_name, "unsubscribed"]),
                (yield contact_proxy.raw_search(
                    "subscription-%s:unsubscribed" % (
                        campaign_name,)).get_count()))

        yield self.collect_message_metrics(conv)
