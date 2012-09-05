# -*- test-case-name: go.apps.sequential_send.tests.test_vumi_app -*-

import json
from datetime import datetime

from twisted.internet.defer import inlineCallbacks, returnValue, gatherResults
from twisted.internet.task import LoopingCall

from vumi import log
from vumi.persist.txredis_manager import TxRedisManager

from go.vumitools.app_worker import GoApplicationWorker


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

    # For test purposes.
    _clock = None

    def validate_config(self):
        super(SequentialSendApplication, self).validate_config()
        self.r_config = self.config.get('redis_manager', {})
        self.poll_interval = self.config.get('poll_interval', 60)

    def _setup_poller(self):
        self.poller = LoopingCall(self.poll_conversations)
        if self._clock is not None:
            # So we can stub in a fake clock.
            self.poller.clock = self._clock
        self.poller.start(self.poll_interval, now=False)

    @inlineCallbacks
    def setup_application(self):
        redis = yield TxRedisManager.from_config(self.r_config)
        self.redis = redis.sub_manager(self.worker_name)
        yield self._go_setup_application()
        self._setup_poller()
        # Store the current time so we don't process stale events.
        yield self.get_interval()

    @inlineCallbacks
    def teardown_application(self):
        yield self._go_teardown_application()
        yield self.poller.stop()
        yield self.redis._close()

    def consume_user_message(self, message):
        # This should not receive inbound messages.
        log.msg('WARNING: Received inbound message: %s' % (message,))

    def consume_ack(self, event):
        return self.vumi_api.mdb.add_event(event)

    def consume_delivery_report(self, event):
        return self.vumi_api.mdb.add_event(event)

    @inlineCallbacks
    def get_interval(self):
        now = self.poller.clock.seconds()
        then = yield self.redis.get('last_poll_time')
        if then is not None:
            then = float(then)
        yield self.redis.set('last_poll_time', now)
        returnValue((then, now))

    def get_conversations(self, conv_pointers):
        return gatherResults([self.get_conversation(batch_id, conv_key)
                              for batch_id, conv_key in conv_pointers])

    @inlineCallbacks
    def poll_conversations(self):
        then, now = yield self.get_interval()
        conv_jsons = yield self.redis.smembers('scheduled_conversations')
        conversations = yield self.get_conversations(
            [json.loads(c) for c in conv_jsons])
        for conv in conversations:
            yield self.process_conversation_schedule(then, now, conv)

    @inlineCallbacks
    def process_conversation_schedule(self, then, now, conv):
        schedule = conv.metadata['schedule']
        if ScheduleManager(schedule).is_scheduled(then, now):
            yield self.send_scheduled_messages(conv)

    @inlineCallbacks
    def send_scheduled_messages(self, conv):
        batch_id = conv.get_batch_keys()[0]
        to_addresses = yield conv.get_opted_in_addresses()
        to_addresses = set(to_addresses)
        for to_addr in to_addresses:
            yield self.send_message(batch_id, to_addr, 'foo', {})

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
                        'on a bulk sequential send.')
            return

        yield self.redis.sadd('scheduled_conversations', json.dumps(
                [batch_id, conversation_key]))
