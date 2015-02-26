# -*- test-case-name: go.apps.sequential_send.tests.test_vumi_app -*-

import json

from twisted.internet.defer import inlineCallbacks, returnValue, gatherResults
from twisted.internet.task import LoopingCall

from vumi import log
from vumi.config import ConfigInt, ConfigDict, ConfigList
from vumi.components.schedule_manager import ScheduleManager

from go.vumitools.app_worker import GoApplicationWorker


class SequentialSendConfig(GoApplicationWorker.CONFIG_CLASS):
    poll_interval = ConfigInt(
        "Interval between polling watched conversations for scheduled events.",
        default=60, static=True)

    schedule = ConfigDict("Scheduler config.")
    messages = ConfigList("List of messages to send in sequence")


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

    CONFIG_CLASS = SequentialSendConfig
    worker_name = 'sequential_send_application'

    def _setup_poller(self):
        self.poller = LoopingCall(self.poll_conversations)
        self.poller.start(self.get_static_config().poll_interval, now=False)

    @inlineCallbacks
    def setup_application(self):
        yield super(SequentialSendApplication, self).setup_application()
        self.redis = self.redis.sub_manager(self.worker_name)
        self._setup_poller()
        # Store the current time so we don't process stale events.
        yield self.get_interval()

    @inlineCallbacks
    def teardown_application(self):
        yield self.poller.stop()
        yield super(SequentialSendApplication, self).teardown_application()

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

    @inlineCallbacks
    def get_conversations(self, conv_pointers):
        results = yield gatherResults([
            self.get_conversation(account_key, conv_key)
            for account_key, conv_key in conv_pointers])
        conversations = []
        for pointer, conv in zip(conv_pointers, results):
            if conv is None:
                log.warning("Conversation %s for account %s not found." % (
                    pointer[1], pointer[0]))
            else:
                conversations.append(conv)
        returnValue(conversations)

    def _get_scheduled_conversations(self):
        return self.redis.smembers('scheduled_conversations')

    @inlineCallbacks
    def poll_conversations(self):
        then, now = yield self.get_interval()
        conv_jsons = yield self._get_scheduled_conversations()
        conversations = yield self.get_conversations(
            [json.loads(c) for c in conv_jsons])
        log.debug("Processing %s to %s: %s" % (
            then, now, [c.key for c in conversations]))
        for conv in conversations:
            if conv.active():
                yield self.process_conversation_schedule(then, now, conv)

    @inlineCallbacks
    def process_conversation_schedule(self, then, now, conv):
        schedule = self.get_config_for_conversation(conv).schedule
        if ScheduleManager(schedule).is_scheduled(then, now):
            yield self.send_scheduled_messages(conv)

    @inlineCallbacks
    def send_scheduled_messages(self, conv):
        config = self.get_config_for_conversation(conv)
        messages = config.messages
        message_options = {}
        conv.set_go_helper_metadata(
            message_options.setdefault('helper_metadata', {}))

        for contacts in (yield conv.get_opted_in_contact_bunches(
                conv.delivery_class)):
            for contact in (yield contacts):
                index_key = 'scheduled_message_index_%s' % (conv.key,)
                message_index = int(contact.extra[index_key] or '0')
                if message_index >= len(messages):
                    # We have nothing more to send to this person.
                    continue

                to_addr = contact.addr_for(conv.delivery_class)
                if not to_addr:
                    log.info("No suitable address found for contact %s %r" % (
                        contact.key, contact,))
                    continue

                yield self.send_message(
                    conv.batch.key, to_addr, messages[message_index],
                    message_options)

                contact.extra[index_key] = u'%s' % (message_index + 1)
                yield contact.save()

    @inlineCallbacks
    def send_message(self, batch_id, to_addr, content, msg_options):
        msg = yield self.send_to(
            to_addr, content, endpoint='default', **msg_options)
        yield self.vumi_api.mdb.add_outbound_message(msg, batch_id=batch_id)
        log.info('Stored outbound %s' % (msg,))

    @inlineCallbacks
    def process_command_start(self, cmd_id, user_account_key,
                              conversation_key):
        yield super(SequentialSendApplication, self).process_command_start(
            cmd_id, user_account_key, conversation_key)

        log.debug("Scheduling conversation: %s" % (conversation_key,))
        yield self.redis.sadd('scheduled_conversations', json.dumps(
            [user_account_key, conversation_key]))

    @inlineCallbacks
    def process_command_stop(self, cmd_id, user_account_key, conversation_key):
        yield super(SequentialSendApplication, self).process_command_stop(
            cmd_id, user_account_key, conversation_key)

        log.debug("Unscheduling conversation: %s" % (conversation_key,))
        yield self.redis.srem('scheduled_conversations', json.dumps(
            [user_account_key, conversation_key]))
