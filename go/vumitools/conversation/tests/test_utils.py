from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportMessage
from vumi.application.tests.test_base import DummyApplicationWorker

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApi, VumiUserApi
from go.vumitools.conversation.utils import ConversationWrapper


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
        self.user_api = yield VumiUserApi(self.api, self.user.key)
        yield self.declare_tags()

        raw_conv = yield self.user_api.conversation_store.new_conversation(
            u'bulk_message', u'subject', u'message',
            delivery_tag_pool=u'longcode', delivery_class=u'sms')
        self.conv = ConversationWrapper(raw_conv, self.user_api)

    @inlineCallbacks
    def declare_tags(self):
        """Declare a set of long codes to the tag pool."""
        yield self.api.declare_tags([("longcode", "default%s" % i) for i
                          in range(10001, 10001 + 4)])
        yield self.api.set_pool_metadata("longcode", {
            "display_name": "Long code",
            "delivery_class": "sms",
            "transport_type": "sms",
            "server_initiated": True,
            })

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
    def test_replies(self):
        yield self.conv.start()
        batch_key = self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20)
        replies = yield self.conv.replies(batch_key=batch_key)
        self.assertEqual(len(replies), 20)
        self.assertEqual(
            len((yield self.conv.replies(0, 5, batch_key=batch_key))), 5)
        self.assertEqual(
            len((yield self.conv.replies(5, 5, batch_key=batch_key))), 5)
        self.assertEqual(
            len((yield self.conv.replies(20, 5, batch_key=batch_key))), 0)
