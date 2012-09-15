# -*- test-case-name: go.apps.sequential_send.tests.test_vumi_app -*-

import json
from datetime import datetime

from twisted.internet.defer import inlineCallbacks, returnValue, gatherResults
from twisted.internet.task import LoopingCall

from vumi import log

from go.vumitools.app_worker import GoApplicationWorker
from go.vumitools.opt_out import OptOutStore
from go.vumitools.contact import ContactStore


class ScheduleManager(object):
    def __init__(self, schedule_definition):
        self.schedule_definition = schedule_definition

    def is_scheduled(self, then, now):
        assert self.schedule_definition['recurring'] == 'daily'
        now_dt = datetime.utcfromtimestamp(now)
        then_dt = datetime.utcfromtimestamp(then)
        tick = datetime.strptime(
            self.schedule_definition['time'], '%H:%M:%S').time()

        tick_dt = datetime.combine(then_dt.date(), tick)
        if tick_dt < then_dt:
            tick_dt = datetime.combine(then_dt.date(), tick)

        return (then_dt < tick_dt <= now_dt)


class SequentialSendApplication(GoApplicationWorker):
    """Send sequential scheduled messages.

    TODO: Figure out this stuff in more detail.

    The conversation should contain the following information:

     * Schedule definition. (How?)

     * List of message copy.

    The poller polls every `poll_interval` seconds and checks the schedule of
    each conversation it's watching. Any conversations that are scheduled to
    send between the last poll time and the current time are processed
    accordingly.
    """

    SEND_TO_TAGS = frozenset(['default'])
    worker_name = 'sequential_send_app'

    def validate_config(self):
        super(SequentialSendApplication, self).validate_config()
        self.poll_interval = self.config.get('poll_interval', 60)

    def _setup_poller(self):
        self.poller = LoopingCall(self.poll_conversations)
        self.poller.start(self.poll_interval, now=False)

    @inlineCallbacks
    def setup_application(self):
        yield self._go_setup_application()
        self.redis = self.redis.sub_manager(self.worker_name)
        self._setup_poller()
        # Store the current time so we don't process stale events.
        yield self.get_interval()

    @inlineCallbacks
    def teardown_application(self):
        yield self.poller.stop()
        yield self._go_teardown_application()

    def consume_user_message(self, message):
        # This should not receive inbound messages.
        log.msg('WARNING: Received inbound message: %s' % (message,))

    def consume_ack(self, event):
        return self.vumi_api.mdb.add_event(event)

    def consume_delivery_report(self, event):
        return self.vumi_api.mdb.add_event(event)

    def _get_last_poll_time(self):
        return self.redis.get('last_poll_time')

    def _set_last_poll_time(self, now):
        return self.redis.set('last_poll_time', now)

    @inlineCallbacks
    def get_interval(self):
        now = self.poller.clock.seconds()
        then = yield self._get_last_poll_time()
        if then is not None:
            then = float(then)
        yield self._set_last_poll_time(now)
        returnValue((then, now))

    def get_conversations(self, conv_pointers):
        return gatherResults([self.get_conversation(batch_id, conv_key)
                              for batch_id, conv_key in conv_pointers])

    def _get_scheduled_conversations(self):
        return self.redis.smembers('scheduled_conversations')

    @inlineCallbacks
    def poll_conversations(self):
        then, now = yield self.get_interval()
        conv_jsons = yield self._get_scheduled_conversations()
        conversations = yield self.get_conversations(
            [json.loads(c) for c in conv_jsons])
        for conv in conversations:
            yield self.process_conversation_schedule(then, now, conv)

    @inlineCallbacks
    def process_conversation_schedule(self, then, now, conv):
        schedule = conv.get_metadata()['schedule']
        if ScheduleManager(schedule).is_scheduled(then, now):
            yield self.send_scheduled_messages(conv)

    @inlineCallbacks
    def send_scheduled_messages(self, conv):
        messages = conv.get_metadata()['messages']
        batch_id = conv.get_batch_keys()[0]
        contacts = yield self.get_contacts_with_addresses(conv)

        for contact, to_addr in contacts:
            index_key = 'scheduled_message_index_%s' % (conv.key,)
            message_index = int(contact.extra[index_key] or '0')
            if message_index >= len(messages):
                # We have nothing more to send to this person.
                continue

            yield self.send_message(
                batch_id, to_addr, messages[message_index], {})

            contact.extra[index_key] = u'%s' % (message_index + 1)
            yield contact.save()

    @inlineCallbacks
    def get_contacts_with_addresses(self, conv):
        """Get opted-in contacts with their addresses.

        Since the account-level opt-out is per-address, we need to look up the
        addresses in here. Once we have them, we may as well return them.
        """
        # FIXME: We need a more generic way to do this.
        opt_out_store = OptOutStore(
            conv.api.manager, conv.user_api.user_account_key)
        optouts = yield opt_out_store.list_opt_outs()
        optout_addrs = [optout.key.split(':', 1)[1] for optout in optouts
                        if optout.key.startswith('msisdn:')]

        contact_store = ContactStore(
            conv.api.manager, conv.user_api.user_account_key)
        contacts = yield contact_store.get_contacts_for_conversation(conv)
        result = []
        for contact in contacts:
            addr = contact.addr_for(conv.delivery_class)
            if addr not in optout_addrs:
                result.append((contact, addr))
        returnValue(result)

    @inlineCallbacks
    def send_message(self, batch_id, to_addr, content, msg_options):
        msg = yield self.send_to(to_addr, content, **msg_options)
        yield self.vumi_api.mdb.add_outbound_message(msg, batch_id=batch_id)
        log.info('Stored outbound %s' % (msg,))

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):

        if is_client_initiated:
            log.warning('Trying to start a client initiated conversation '
                        'on a sequential send.')
            return

        yield self.redis.sadd('scheduled_conversations', json.dumps(
                [batch_id, conversation_key]))
