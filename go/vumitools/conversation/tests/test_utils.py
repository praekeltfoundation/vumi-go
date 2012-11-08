from twisted.trial.unittest import SkipTest
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportMessage
from vumi.application.tests.test_base import DummyApplicationWorker

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApi
from go.vumitools.conversation.utils import ConversationWrapper
from go.vumitools.exceptions import ConversationSendError


class ConversationWrapperTestCase(AppWorkerTestCase):

    application_class = DummyApplicationWorker

    @inlineCallbacks
    def setUp(self):
        yield super(ConversationWrapperTestCase, self).setUp()
        self.manager = yield self.get_riak_manager()
        self.redis = yield self.get_redis_manager()

        # Get a dummy worker so we have an amqp_client which we need
        # to set-up the MessageSender in the `VumiApi`
        self.worker = yield self.get_application({})
        self.api = yield VumiApi.from_config_async(self.mk_config({}),
            amqp_client=self.worker._amqp_client)
        self.mdb = self.api.mdb
        self.user = yield self.mk_user(self.api, u'username')
        self.user_api = self.api.get_user_api(self.user.key)
        yield self.declare_tags()

        raw_conv = yield self.user_api.conversation_store.new_conversation(
            u'bulk_message', u'subject', u'message',
            delivery_tag_pool=u'longcode', delivery_class=u'sms')
        self.conv = ConversationWrapper(raw_conv, self.user_api)

    @inlineCallbacks
    def declare_tags(self, name='longcode', count=4, metadata=None):
        """Declare a set of long codes to the tag pool."""
        yield self.api.declare_tags([(name, "%s%s" % (name, i)) for i
                          in range(10001, 10001 + count)])
        defaults = {
            "display_name": name,
            "delivery_class": "sms",
            "transport_type": "sms",
            "server_initiated": True,
            }
        defaults.update(metadata or {})
        yield self.api.set_pool_metadata(name, defaults)

    @inlineCallbacks
    def store_inbound(self, batch_key, count=10, addr_template='from-{0}'):
        inbound = []
        for i in range(count):
            msg_in = self.mkmsg_in(from_addr=addr_template.format(i),
                message_id=TransportMessage.generate_id())
            yield self.mdb.add_inbound_message(msg_in, batch_id=batch_key)
            inbound.append(msg_in)
        returnValue(inbound)

    @inlineCallbacks
    def store_outbound(self, batch_key, count=10, addr_template='to-{0}'):
        outbound = []
        for i in range(count):
            msg_out = self.mkmsg_out(to_addr=addr_template.format(i),
                message_id=TransportMessage.generate_id())
            yield self.mdb.add_outbound_message(msg_out, batch_id=batch_key)
            outbound.append(msg_out)
        returnValue(outbound)

    @inlineCallbacks
    def store_event(self, outbound, event_type, count=None, **kwargs):
        count = count or len(outbound)
        messages = outbound[0:count]
        events = []
        for message in messages:
            event_maker = getattr(self, 'mkmsg_%s' % (event_type,))
            event = event_maker(user_message_id=message['message_id'],
                **kwargs)
            yield self.mdb.add_event(event)
            events.append(event)
        returnValue(events)

    def test_get_latest_batch_key(self):
        batch_key = self.conv.get_latest_batch_key()
        self.assertEqual(batch_key, None)
        self.assertEqual(self.conv.batches.keys(), [])

        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        self.assertNotEqual(batch_key, None)
        self.assertLen(self.conv.batches.keys(), 1)

    @inlineCallbacks
    def test_count_replies(self):
        yield self.conv.start()
        yield self.store_inbound(self.conv.get_latest_batch_key())
        self.assertEqual((yield self.conv.count_replies()), 10)

    @inlineCallbacks
    def test_count_sent_messages(self):
        yield self.conv.start()
        yield self.store_outbound(self.conv.get_latest_batch_key())
        self.assertEqual((yield self.conv.count_sent_messages()), 10)

    @inlineCallbacks
    def test_count_inbound_uniques(self):
        yield self.conv.start()
        yield self.store_inbound(self.conv.get_latest_batch_key(), count=5)
        self.assertEqual((yield self.conv.count_inbound_uniques()), 5)
        yield self.store_inbound(self.conv.get_latest_batch_key(), count=5,
            addr_template='from')
        self.assertEqual((yield self.conv.count_inbound_uniques()), 6)

    @inlineCallbacks
    def test_count_outbound_uniques(self):
        yield self.conv.start()
        yield self.store_outbound(self.conv.get_latest_batch_key(), count=5)
        self.assertEqual((yield self.conv.count_outbound_uniques()), 5)
        yield self.store_outbound(self.conv.get_latest_batch_key(), count=5,
            addr_template='from')
        self.assertEqual((yield self.conv.count_outbound_uniques()), 6)

    @inlineCallbacks
    def test_received_messages(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20)
        received_messages = yield self.conv.received_messages()
        self.assertEqual(len(received_messages), 20)
        self.assertEqual(len((yield self.conv.received_messages(0, 5))), 5)
        self.assertEqual(len((yield self.conv.received_messages(5, 10))), 5)
        self.assertEqual(len((yield self.conv.received_messages(20, 25))), 0)

    @inlineCallbacks
    def test_received_messages_dictionary(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        [msg] = yield self.store_inbound(batch_key, count=1)
        [reply] = yield self.conv.received_messages()
        self.assertEqual(reply['type'], self.conv.delivery_class),
        self.assertEqual(reply['source'],
            (yield self.conv.delivery_class_description()))
        self.assertEqual(reply['content'], msg['content'])

    @inlineCallbacks
    def test_sent_messages(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20)
        sent_messages = yield self.conv.sent_messages()
        self.assertEqual(len(sent_messages), 20)
        self.assertEqual(len((yield self.conv.sent_messages(0, 5))), 5)
        self.assertEqual(len((yield self.conv.sent_messages(5, 10))), 5)
        self.assertEqual(len((yield self.conv.sent_messages(20, 25))), 0)

    @inlineCallbacks
    def test_sent_messages_dictionary(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        [msg] = yield self.store_outbound(batch_key, count=1)
        [sent_message] = yield self.conv.sent_messages()
        self.assertEqual(sent_message['type'], self.conv.delivery_class),
        self.assertEqual(sent_message['source'],
            (yield self.conv.delivery_class_description()))
        self.assertEqual(sent_message['content'], msg['content'])

    @inlineCallbacks
    def test_get_tags(self):
        yield self.conv.start()
        [tag] = yield self.conv.get_tags()
        self.assertEqual(tag, ('longcode', 'longcode10001'))

    @inlineCallbacks
    def test_get_progress_status(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        outbound = yield self.store_outbound(batch_key, count=10)
        yield self.store_event(outbound, 'ack', count=8)
        yield self.store_event(outbound, 'nack', count=2)
        yield self.store_event(outbound, 'delivery', count=4,
            status='delivered')
        yield self.store_event(outbound, 'delivery', count=1,
            status='failed')
        yield self.store_event(outbound, 'delivery', count=1,
            status='pending')
        self.assertEqual((yield self.conv.get_progress_status()), {
            'sent': 10,
            'ack': 8,
            'nack': 2,
            'delivery_report': 6,
            'delivery_report_delivered': 4,
            'delivery_report_failed': 1,
            'delivery_report_pending': 1,
            })

    @inlineCallbacks
    def test_get_progress_percentage(self):
        yield self.conv.start()
        self.assertEqual((yield self.conv.get_progress_percentage()), 0)
        batch_key = self.conv.get_latest_batch_key()
        outbound = yield self.store_outbound(batch_key, count=10)
        yield self.store_event(outbound, 'ack', count=8)
        self.assertEqual((yield self.conv.get_progress_percentage()), 80)

    @inlineCallbacks
    def test_acquire_tag(self):
        tag = yield self.conv.acquire_tag()
        self.assertEqual(tag, ('longcode', 'longcode10001'))

    @inlineCallbacks
    def test_acquire_tag_if_none_available(self):
        yield self.declare_tags("shortcode", count=0)
        self.conv.c.delivery_tag_pool = u"shortcode"
        yield self.conv.save()
        yield self.assertFailure(self.conv.acquire_tag(),
            ConversationSendError)

    @inlineCallbacks
    def test_acquire_tag_if_tag_unavailable(self):
        self.conv.c.delivery_tag_pool = u"longcode"
        self.conv.c.delivery_tag = u'this-does-not-exist'
        yield self.conv.save()
        yield self.assertFailure(self.conv.acquire_tag(),
            ConversationSendError)

    def test_get_opted_in_contacts(self):
        raise SkipTest("Waiting for API to stabilize")

    def test_get_opted_in_addresses(self):
        raise SkipTest("Waiting for API to stabilize")

    @inlineCallbacks
    def test_get_inbound_throughput(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20)
        # 20 messages in 5 minutes = 4 messages per minute
        self.assertEqual(
            (yield self.conv.get_inbound_throughput()), 4)
        # 20 messages in 20 seconds = 60 messages per minute
        self.assertEqual(
            (yield self.conv.get_inbound_throughput(sample_time=20)), 60)

    @inlineCallbacks
    def test_get_outbound_throughput(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20)
        # 20 messages in 5 minutes = 4 messages per minute
        self.assertEqual(
            (yield self.conv.get_outbound_throughput()), 4)
        # 20 messages in 20 seconds = 60 messages per minute
        self.assertEqual(
            (yield self.conv.get_outbound_throughput(sample_time=20)), 60)
