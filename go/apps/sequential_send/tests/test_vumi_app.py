"""Tests for go.apps.sequential_send.vumi_app"""

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import Clock, LoopingCall

from vumi.message import TransportUserMessage
from vumi.tests.helpers import VumiTestCase
from vumi.tests.utils import LogCatcher

from go.apps.sequential_send.vumi_app import SequentialSendApplication
from go.apps.sequential_send import vumi_app as sequential_send_module
from go.apps.tests.helpers import AppWorkerHelper


class TestSequentialSendApplication(VumiTestCase):

    transport_type = u'sms'

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(
            AppWorkerHelper(SequentialSendApplication))
        self.clock = Clock()
        self.patch(sequential_send_module, 'LoopingCall', self.looping_call)
        self.app = yield self.app_helper.get_app_worker({})

    def looping_call(self, *args, **kwargs):
        looping_call = LoopingCall(*args, **kwargs)
        looping_call.clock = self.clock
        return looping_call

    @inlineCallbacks
    def reply_to(self, msg, content, continue_session=True, **kw):
        session_event = (None if continue_session
                         else TransportUserMessage.SESSION_CLOSE)
        reply = TransportUserMessage(
            to_addr=msg['from_addr'],
            from_addr=msg['to_addr'],
            group=msg['group'],
            in_reply_to=msg['message_id'],
            content=content,
            session_event=session_event,
            transport_name=msg['transport_name'],
            transport_type=msg['transport_type'],
            transport_metadata=msg['transport_metadata'],
            helper_metadata=msg['helper_metadata'],
            **kw)
        yield self.dispatch(reply)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.wait_for_dispatched_messages(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def _stub_out_async(self, *convs):
        """Stub out async components.

        NOTE: Riak stuff takes a while and messes up fake clock timing, so we
        stub it out. It gets tested in other test methods. Also, we replace the
        redis manager for the same reason.
        """

        # Avoid hitting Riak for the conversation and Redis for poll times.
        expected = [[conv.user_account.key, conv.key] for conv in convs]
        poll_times = [(yield self.app._get_last_poll_time())]
        scheduled_conversations = yield self.app._get_scheduled_conversations()

        def get_conversations(conv_pointers):
            self.assertEqual(sorted(conv_pointers), sorted(expected))
            return list(convs)
        self.app.get_conversations = get_conversations

        self.app._get_last_poll_time = lambda: poll_times[-1]
        self.app._set_last_poll_time = lambda t: poll_times.append(str(t))
        self.app._get_scheduled_conversations = lambda: scheduled_conversations

        self.message_convs = []

        # Fake the message send by adding the convs to a list.
        def send_scheduled_messages(sched_conv):
            self.message_convs.append(sched_conv)
        self.app.send_scheduled_messages = send_scheduled_messages

    def _patch_with_raise_once(self, obj, attr, err):
        def raiser(*args, **kw):
            patch.restore()
            raise err
        patch = self.patch(obj, attr, raiser)
        return err

    def check_message_convs_and_advance(self, convs, seconds):
        self.assertEqual(convs, self.message_convs)
        return self.clock.advance(seconds)

    @inlineCallbacks
    def test_schedule_daily_conv(self):
        conv = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv)
        conv = yield self.app_helper.get_conversation(conv.key)

        yield self._stub_out_async(conv)

        yield self.check_message_convs_and_advance([], 70)
        yield self.check_message_convs_and_advance([], 70)
        yield self.check_message_convs_and_advance([conv], 70)
        yield self.check_message_convs_and_advance([conv], 3600 * 24 - 140)
        yield self.check_message_convs_and_advance([conv], 70)
        yield self.check_message_convs_and_advance([conv, conv], 70)
        self.assertEqual(self.message_convs, [conv, conv])

    @inlineCallbacks
    def test_schedule_daily_with_stopped_conv(self):
        conv = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv)
        conv = yield self.app_helper.get_conversation(conv.key)
        yield self.app_helper.stop_conversation(conv)
        conv = yield self.app_helper.get_conversation(conv.key)

        yield self._stub_out_async()

        yield self.check_message_convs_and_advance([], 70)
        yield self.check_message_convs_and_advance([], 70)
        # had it been scheduled it should show up after from here on onwards
        yield self.check_message_convs_and_advance([], 70)
        yield self.check_message_convs_and_advance([], 3600 * 24 - 140)
        yield self.check_message_convs_and_advance([], 70)
        yield self.check_message_convs_and_advance([], 70)
        self.assertEqual(self.message_convs, [])

    @inlineCallbacks
    def test_schedule_day_of_month_conv(self):
        conv = yield self.app_helper.create_conversation(config={
            'schedule': {
                'recurring': 'day_of_month',
                'time': '12:00:00', 'days':
                '1, 5',
            },
        })
        yield self.app_helper.start_conversation(conv)
        conv = yield self.app_helper.get_conversation(conv.key)

        yield self._stub_out_async(conv)

        yield self.check_message_convs_and_advance([], 3600 * 11)
        yield self.check_message_convs_and_advance([], 3600 * 13)
        yield self.check_message_convs_and_advance([conv], 3600 * 24)
        yield self.check_message_convs_and_advance([conv], 3600 * 48)
        yield self.check_message_convs_and_advance([conv], 3600 * 13)
        yield self.check_message_convs_and_advance([conv, conv], 3600 * 11)
        yield self.check_message_convs_and_advance(
            [conv, conv], 3600 * 24 * 20)
        self.assertEqual(self.message_convs, [conv, conv])

    @inlineCallbacks
    def test_schedule_convs(self):
        """Test multiple conversation scheduling.

        NOTE: Riak stuff takes a while and messes up fake clock timing, so we
        stub it out. It gets tested in other test methods.
        """
        conv1 = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv1)
        conv1 = yield self.app_helper.get_conversation(conv1.key)

        conv2 = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:02:30'}})
        yield self.app_helper.start_conversation(conv2)
        conv2 = yield self.app_helper.get_conversation(conv2.key)

        yield self._stub_out_async(conv1, conv2)

        yield self.check_message_convs_and_advance([], 70)
        yield self.check_message_convs_and_advance([], 70)
        yield self.check_message_convs_and_advance([conv1], 70)
        yield self.check_message_convs_and_advance(
            [conv1, conv2], 3600 * 24 - 140)
        yield self.check_message_convs_and_advance([conv1, conv2], 70)
        yield self.check_message_convs_and_advance([conv1, conv2, conv1], 70)
        self.assertEqual(self.message_convs, [conv1, conv2, conv1, conv2])

    @inlineCallbacks
    def test_poll_conversations_errors(self):
        """Test that polling for conversations continues after errors."""
        conv1 = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv1)
        conv1 = yield self.app_helper.get_conversation(conv1.key)

        yield self._stub_out_async(conv1)

        yield self.check_message_convs_and_advance([], 70)
        self.assertEqual(self.flushLoggedErrors(), [])

        err = self._patch_with_raise_once(
            self.app, 'get_conversations', ValueError("Failed"))

        yield self.check_message_convs_and_advance([], 70)
        [failure] = self.flushLoggedErrors()
        self.assertEqual(failure.value, err)

        # no conversations processed initially because of the error
        yield self.check_message_convs_and_advance([], 3600 * 24 - 70)
        yield self.check_message_convs_and_advance([], 70)
        # now a conversation has been processed
        self.assertEqual(self.message_convs, [conv1])

    @inlineCallbacks
    def test_process_conversation_schedule_errors(self):
        """
        Test that errors for one conversation do not prevent other
        conversations sending messages.
        """
        conv1 = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv1)
        conv1 = yield self.app_helper.get_conversation(conv1.key)

        conv2 = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv2)
        conv2 = yield self.app_helper.get_conversation(conv2.key)

        yield self._stub_out_async(conv1, conv2)

        err = self._patch_with_raise_once(
            self.app, 'send_scheduled_messages', ValueError("Failed"))

        self.assertEqual(self.message_convs, [])

        yield self.check_message_convs_and_advance([], 140)
        [failure] = self.flushLoggedErrors()
        self.assertEqual(failure.value, err)

        self.assertEqual(self.message_convs, [conv2])

    @inlineCallbacks
    def test_get_conversations(self):
        """Test get_conversation, because we stub it out elsewhere.
        """

        conv1 = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv1)

        conv2 = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:02:30'}})
        yield self.app_helper.start_conversation(conv2)

        yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:02:30'}})

        convs = yield self.app.get_conversations([
            [conv1.user_account.key, conv1.key],
            [conv2.user_account.key, conv2.key]])

        self.assertEqual(sorted([c.key for c in convs]),
                         sorted([conv1.key, conv2.key]))

    @inlineCallbacks
    def test_get_conversations_missing_conv(self):
        """
        Test get_conversation when it's expecting a conversation that doesn't
        exist.
        """
        conv = yield self.app_helper.create_conversation(
            config={'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield self.app_helper.start_conversation(conv)

        with LogCatcher(message='Conversation .* not found.') as lc:
            convs = yield self.app.get_conversations(
                [[conv.user_account.key, conv.key], ['badaccount', 'badkey']])
            self.assertEqual(
                lc.messages(),
                ['Conversation badkey for account badaccount not found.'])

        self.assertEqual([c.key for c in convs], [conv.key])

    @inlineCallbacks
    def test_sends(self):
        """Test send_scheduled_messages, because we stub it out elsewhere.
        """
        group = yield self.app_helper.create_group(u'group')
        contact1 = yield self.app_helper.create_contact(
            u'27831234567', name=u'First', surname=u'Contact', groups=[group])
        contact2 = yield self.app_helper.create_contact(
            u'27831234568', name=u'Second', surname=u'Contact', groups=[group])

        conv = yield self.app_helper.create_conversation(config={
            'schedule': {'recurring': 'daily', 'time': '00:01:40'},
            'messages': ['foo', 'bar'],
        }, groups=[group])
        yield self.app_helper.start_conversation(conv)
        conv = yield self.app_helper.get_conversation(conv.key)

        # Send to two contacts.
        yield self.app.send_scheduled_messages(conv)

        [msg1, msg2] = sorted(
            self.app_helper.get_dispatched_outbound(),
            key=lambda m: m['to_addr'])
        self.assertEqual(msg1['content'], 'foo')
        self.assertEqual(msg1['to_addr'], contact1.msisdn)
        self.assertEqual(msg1['helper_metadata']['go'], {
            'user_account': conv.user_account.key,
            'conversation_type': 'sequential_send',
            'conversation_key': conv.key,
        })
        self.assertEqual(msg2['content'], 'foo')
        self.assertEqual(msg2['to_addr'], contact2.msisdn)
        self.assertEqual(msg2['helper_metadata']['go'], {
            'user_account': conv.user_account.key,
            'conversation_type': 'sequential_send',
            'conversation_key': conv.key,
        })

        # Send to previous two contacts and a new third contact.
        contact3 = yield self.app_helper.create_contact(
            u'27831234569', name=u'Third', surname=u'Contact', groups=[group])
        yield self.app.send_scheduled_messages(conv)

        [msg1, msg2, msg3] = sorted(
            self.app_helper.get_dispatched_outbound()[2:],
            key=lambda m: m['to_addr'])
        self.assertEqual(msg1['content'], 'bar')
        self.assertEqual(msg1['to_addr'], contact1.msisdn)
        self.assertEqual(msg2['content'], 'bar')
        self.assertEqual(msg2['to_addr'], contact2.msisdn)
        self.assertEqual(msg3['content'], 'foo')
        self.assertEqual(msg3['to_addr'], contact3.msisdn)

        # Previous two contacts are done, so we should only send to the third.
        yield self.app.send_scheduled_messages(conv)

        [msg] = sorted(
            self.app_helper.get_dispatched_outbound()[5:],
            key=lambda m: m['to_addr'])
        self.assertEqual(msg['content'], 'bar')
        self.assertEqual(msg['to_addr'], contact3.msisdn)
