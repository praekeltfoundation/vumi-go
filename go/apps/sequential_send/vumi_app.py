# -*- test-case-name: go.apps.sequential_send.tests.test_vumi_app -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall

from vumi import log
from vumi.persist.txredis_manager import TxRedisManager

from go.vumitools.app_worker import GoApplicationWorker


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

    @inlineCallbacks
    def poll_conversations(self):
        then, now = yield self.get_interval()
        print "Interval:", then, now
        tick = 100. * int(now / 100)
        if then < tick <= now:
            print "  EVENT!"

    def process_conversation_schedule(self, conversation):
        pass

    @inlineCallbacks
    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):

        if is_client_initiated:
            log.warning('Trying to start a client initiated conversation '
                        'on a bulk sequential send.')
            return

        # TODO: Implement this.
        assert False

        conv = yield self.get_conversation(batch_id, conversation_key)

        to_addresses = yield conv.get_opted_in_addresses()
        if extra_params.get('dedupe') == True:
            to_addresses = set(to_addresses)
        for to_addr in to_addresses:
            yield self.send_message(batch_id, to_addr,
                                    conv.message, msg_options)
