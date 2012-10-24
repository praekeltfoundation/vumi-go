"""Tests for go.apps.sequential_send.vumi_app"""

import uuid

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import Clock, LoopingCall

from vumi.message import TransportUserMessage

from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.sequential_send.vumi_app import SequentialSendApplication
from go.apps.sequential_send import vumi_app as sequential_send_module


class TestSequentialSendApplication(AppWorkerTestCase):

    application_class = SequentialSendApplication
    transport_type = u'sms'

    @inlineCallbacks
    def setUp(self):
        super(TestSequentialSendApplication, self).setUp()

        # Setup the SurveyApplication
        self.clock = Clock()
        self.patch(sequential_send_module, 'LoopingCall',
                   self.looping_call)
        self.app = yield self.get_application({
                'worker_name': 'sequential_send_application',
                }, start=False)
        yield self.app.startWorker()

        # Setup the command dispatcher so we cand send it commands
        self.cmd_dispatcher = yield self.get_application({
                'transport_name': 'cmd_dispatcher',
                'worker_names': ['sequential_send_application'],
                }, cls=CommandDispatcher)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!
        self._persist_riak_managers.append(self.vumi_api.manager)

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = VumiUserApi(self.vumi_api, self.user_account.key)

        # Add tags
        self.user_api.api.declare_tags([("pool", "tag1"), ("pool", "tag2")])
        self.user_api.api.set_pool_metadata("pool", {
            "transport_type": self.transport_type,
            "msg_options": {
                "transport_name": self.transport_name,
            },
        })

        # Give a user access to a tagpool
        self.user_api.api.account_store.tag_permissions(uuid.uuid4().hex,
            tagpool=u"pool", max_keys=None)

    def looping_call(self, *args, **kwargs):
        looping_call = LoopingCall(*args, **kwargs)
        looping_call.clock = self.clock
        return looping_call

    @inlineCallbacks
    def create_group(self, name):
        group = yield self.user_api.contact_store.new_group(name)
        yield group.save()
        returnValue(group)

    @inlineCallbacks
    def create_contact(self, name, surname, **kw):
        contact = yield self.user_api.contact_store.new_contact(name=name,
            surname=surname, **kw)
        yield contact.save()
        returnValue(contact)

    @inlineCallbacks
    def create_conversation(self, **kw):
        conversation = yield self.user_api.new_conversation(
            u'sequential_send', u'Subject', u'Message',
            delivery_tag_pool=u'pool', delivery_class=self.transport_type,
            **kw)
        yield conversation.save()
        returnValue(self.user_api.wrap_conversation(conversation))

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
        # Avoid hitting Riak for the conversation and Redis for poll times.
        expected = [[conv.get_batch_keys()[0], conv.key] for conv in convs]
        poll_times = [(yield self.app._get_last_poll_time())]
        scheduled_conversations = yield self.app._get_scheduled_conversations()

        def get_conversations(conv_pointers):
            self.assertEqual(sorted(conv_pointers), sorted(expected))
            return list(convs)
        self.app.get_conversations = get_conversations

        self.app._get_last_poll_time = lambda: poll_times[-1]
        self.app._set_last_poll_time = lambda t: poll_times.append(str(t))
        self.app._get_scheduled_conversations = lambda: scheduled_conversations

    @inlineCallbacks
    def test_schedule_conv(self):
        """Test conversation scheduling.

        NOTE: Riak stuff takes a while and messes up fake clock timing, so we
        stub it out. It gets tested in other test methods. Also, we replace the
        redis manager for the same reason.
        """

        conv = yield self.create_conversation(metadata={
                'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield conv.start()

        yield self._stub_out_async(conv)
        message_convs = []

        # Fake the message send by adding the convs to a list.
        def send_scheduled_messages(conv):
            message_convs.append(conv)
        self.app.send_scheduled_messages = send_scheduled_messages

        self.assertEqual(message_convs, [])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv])
        yield self.clock.advance(3600 * 24 - 140)
        self.assertEqual(message_convs, [conv])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv, conv])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv, conv])

    @inlineCallbacks
    def test_schedule_convs(self):
        """Test multiple conversation scheduling.

        NOTE: Riak stuff takes a while and messes up fake clock timing, so we
        stub it out. It gets tested in other test methods.
        """

        conv1 = yield self.create_conversation(metadata={
                'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield conv1.start()

        conv2 = yield self.create_conversation(metadata={
                'schedule': {'recurring': 'daily', 'time': '00:02:30'}})
        yield conv2.start()

        yield self._stub_out_async(conv1, conv2)
        message_convs = []

        # Fake the message send by adding the convs to a list.
        def send_scheduled_messages(conv):
            message_convs.append(conv)
        self.app.send_scheduled_messages = send_scheduled_messages

        self.assertEqual(message_convs, [])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv1])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv1, conv2])
        yield self.clock.advance(3600 * 24 - 140)
        self.assertEqual(message_convs, [conv1, conv2])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv1, conv2, conv1])
        yield self.clock.advance(70)
        self.assertEqual(message_convs, [conv1, conv2, conv1, conv2])

    @inlineCallbacks
    def test_get_conversations(self):
        """Test get_conversation, because we stub it out elsewhere.
        """
        conv1 = yield self.create_conversation(metadata={
                'schedule': {'recurring': 'daily', 'time': '00:01:40'}})
        yield conv1.start()
        batch_id1 = conv1.get_batch_keys()[0]

        conv2 = yield self.create_conversation(metadata={
                'schedule': {'recurring': 'daily', 'time': '00:02:30'}})
        yield conv2.start()
        batch_id2 = conv2.get_batch_keys()[0]

        yield self.create_conversation(metadata={
                'schedule': {'recurring': 'daily', 'time': '00:02:30'}})

        [c1, c2] = yield self.app.get_conversations(
            [[batch_id1, conv1.key], [batch_id2, conv2.key]])

        self.assertEqual(sorted([c1.key, c2.key]),
                         sorted([conv1.key, conv2.key]))

    @inlineCallbacks
    def test_sends(self):
        """Test send_scheduled_messages, because we stub it out elsewhere.
        """

        group = yield self.create_group(u'group')
        contact1 = yield self.create_contact(name=u'First',
            surname=u'Contact', msisdn=u'27831234567', groups=[group])
        contact2 = yield self.create_contact(name=u'Second',
            surname=u'Contact', msisdn=u'27831234568', groups=[group])

        conv = yield self.create_conversation(metadata={
                'schedule': {'recurring': 'daily', 'time': '00:01:40'},
                'messages': ['foo', 'bar'],
                })
        conv.add_group(group)
        yield conv.start()

        # Send to two contacts.
        yield self.app.send_scheduled_messages(conv)

        [msg1, msg2] = sorted(self.get_dispatched_messages(),
                              key=lambda m: m['to_addr'])
        self.assertEqual(msg1['content'], 'foo')
        self.assertEqual(msg1['to_addr'], contact1.msisdn)
        self.assertEqual(msg2['content'], 'foo')
        self.assertEqual(msg2['to_addr'], contact2.msisdn)

        # Send to previous two contacts and a new third contact.
        contact3 = yield self.create_contact(name=u'Third',
            surname=u'Contact', msisdn=u'27831234569', groups=[group])
        yield self.app.send_scheduled_messages(conv)

        [msg1, msg2, msg3] = sorted(self.get_dispatched_messages()[2:],
                                    key=lambda m: m['to_addr'])
        self.assertEqual(msg1['content'], 'bar')
        self.assertEqual(msg1['to_addr'], contact1.msisdn)
        self.assertEqual(msg2['content'], 'bar')
        self.assertEqual(msg2['to_addr'], contact2.msisdn)
        self.assertEqual(msg3['content'], 'foo')
        self.assertEqual(msg3['to_addr'], contact3.msisdn)

        # Previous two contacts are done, so we should only send to the third.
        yield self.app.send_scheduled_messages(conv)

        [msg] = sorted(self.get_dispatched_messages()[5:],
                       key=lambda m: m['to_addr'])
        self.assertEqual(msg['content'], 'bar')
        self.assertEqual(msg['to_addr'], contact3.msisdn)

    @inlineCallbacks
    def test_collect_metrics(self):
        conv = yield self.create_conversation()
        yield conv.start()
        yield self.dispatch_command(
            'collect_metrics', conversation_key=conv.key,
            user_account_key=self.user_account.key)
        metrics = self.poll_metrics('%s.%s' % (self.user_account.key,
                                               conv.key))
        self.assertEqual({
                u'messages_sent': [0],
                u'messages_received': [0],
                }, metrics)
