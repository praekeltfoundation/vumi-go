from datetime import datetime, timedelta

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
        yield self._declare_tags()

        raw_conv = yield self.user_api.conversation_store.new_conversation(
            u'bulk_message', u'subject', u'message',
            delivery_tag_pool=u'longcode', delivery_class=u'sms')
        self.conv = ConversationWrapper(raw_conv, self.user_api)

    @inlineCallbacks
    def _declare_tags(self, name=u'longcode', count=4, metadata=None):
        """Declare a set of long codes to the tag pool."""
        yield self.declare_tags(self.api, [
            (name, "%s%s" % (name, i)) for i in range(10001, 10001 + count)])
        defaults = {
            "display_name": name,
            "delivery_class": "sms",
            "transport_type": "sms",
            "server_initiated": True,
            }
        defaults.update(metadata or {})
        yield self.set_pool_metadata(self.api, name, defaults)

    @inlineCallbacks
    def get_batch_id(self, conv, tag):
        batch_id = yield conv.start_batch(tag)
        self.conv.batches.add_key(batch_id)
        yield conv.save()
        returnValue(batch_id)

    @inlineCallbacks
    def store_inbound(self, batch_key, count=10, addr_template='from-{0}',
                        content_template='hello world {0}',
                        start_timestamp=None, time_multiplier=10,
                        helper_metadata=None):
        inbound = []
        now = start_timestamp or datetime.now().replace(hour=23, minute=59,
                                                    second=59, microsecond=999)
        for i in range(count):
            msg_in = self.mkmsg_in(from_addr=addr_template.format(i),
                message_id=TransportMessage.generate_id(),
                content=content_template.format(i),
                helper_metadata=helper_metadata)
            msg_in['timestamp'] = now - timedelta(hours=i * time_multiplier)
            yield self.mdb.add_inbound_message(msg_in, batch_id=batch_key)
            inbound.append(msg_in)
        returnValue(inbound)

    @inlineCallbacks
    def store_outbound(self, batch_key, count=10, addr_template='to-{0}',
                        content_template='hello world {0}',
                        start_timestamp=None, time_multiplier=10,
                        helper_metadata=None):
        outbound = []
        now = start_timestamp or datetime.now().replace(hour=23, minute=59,
                                                    second=59, microsecond=999)
        for i in range(count):
            msg_out = self.mkmsg_out(to_addr=addr_template.format(i),
                message_id=TransportMessage.generate_id(),
                content=content_template.format(i),
                helper_metadata=helper_metadata)
            msg_out['timestamp'] = now - timedelta(hours=i * time_multiplier)
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

    @inlineCallbacks
    def test_get_latest_batch_key(self):
        batch_key = yield self.conv.get_latest_batch_key()
        self.assertEqual(batch_key, None)
        self.assertEqual(self.conv.batches.keys(), [])

        tag = yield self.conv.acquire_tag()
        batch1 = yield self.get_batch_id(self.conv, tag)
        batch2 = yield self.get_batch_id(self.conv, tag)

        now = datetime.now()
        yield self.store_outbound(batch1,
                                    start_timestamp=now - timedelta(days=1))
        yield self.store_outbound(batch2, start_timestamp=now)

        conv = yield self.user_api.get_wrapped_conversation(self.conv.key)
        batch_key = yield conv.get_latest_batch_key()
        self.assertEqual(batch_key, batch2)
        self.assertEqual(len(conv.batches.keys()), 2)

    @inlineCallbacks
    def test_count_replies(self):
        yield self.conv.start()
        yield self.store_inbound((yield self.conv.get_latest_batch_key()))
        self.assertEqual((yield self.conv.count_replies()), 10)

    @inlineCallbacks
    def test_count_sent_messages(self):
        yield self.conv.start()
        yield self.store_outbound((yield self.conv.get_latest_batch_key()))
        self.assertEqual((yield self.conv.count_sent_messages()), 10)

    @inlineCallbacks
    def test_count_inbound_uniques(self):
        yield self.conv.start()
        yield self.store_inbound((yield self.conv.get_latest_batch_key()),
                                    count=5)
        self.assertEqual((yield self.conv.count_inbound_uniques()), 5)
        yield self.store_inbound((yield self.conv.get_latest_batch_key()),
                                    count=5, addr_template='from')
        self.assertEqual((yield self.conv.count_inbound_uniques()), 6)

    @inlineCallbacks
    def test_count_outbound_uniques(self):
        yield self.conv.start()
        yield self.store_outbound((yield self.conv.get_latest_batch_key()),
                                    count=5)
        self.assertEqual((yield self.conv.count_outbound_uniques()), 5)
        yield self.store_outbound((yield self.conv.get_latest_batch_key()),
                                    count=5, addr_template='from')
        self.assertEqual((yield self.conv.count_outbound_uniques()), 6)

    @inlineCallbacks
    def test_received_messages(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20)
        received_messages = yield self.conv.received_messages()
        self.assertEqual(len(received_messages), 20)
        self.assertEqual(len((yield self.conv.received_messages(0, 5))), 5)
        self.assertEqual(len((yield self.conv.received_messages(5, 10))), 5)
        self.assertEqual(len((yield self.conv.received_messages(20, 25))), 0)

    @inlineCallbacks
    def test_received_messages_include_sensitive(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20, helper_metadata={
            'go': {
                'sensitive': True,
            }})
        self.assertEqual([], (yield self.conv.received_messages()))
        self.assertEqual(20, len((yield self.conv.received_messages(
                                        include_sensitive=True))))

    @inlineCallbacks
    def test_received_messages_include_sensitive_and_scrub(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20, helper_metadata={
            'go': {
                'sensitive': True,
            }})

        def scrubber(msg):
            msg['content'] = 'scrubbed'
            return msg

        scrubbed_messages = yield self.conv.received_messages(
            include_sensitive=True, scrubber=scrubber)
        self.assertEqual(len(scrubbed_messages), 20)
        for message in scrubbed_messages:
            self.assertEqual(message['content'], 'scrubbed')

    @inlineCallbacks
    def test_received_messages_dictionary(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        [msg] = yield self.store_inbound(batch_key, count=1)
        [reply] = yield self.conv.received_messages()
        self.assertEqual(msg['message_id'], reply['message_id'])

    @inlineCallbacks
    def test_sent_messages(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20)
        sent_messages = yield self.conv.sent_messages()
        self.assertEqual(len(sent_messages), 20)
        self.assertEqual(len((yield self.conv.sent_messages(0, 5))), 5)
        self.assertEqual(len((yield self.conv.sent_messages(5, 10))), 5)
        self.assertEqual(len((yield self.conv.sent_messages(20, 25))), 0)

    @inlineCallbacks
    def test_sent_messages_include_sensitive(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20, helper_metadata={
            'go': {
                'sensitive': True,
            }})
        self.assertEqual([], (yield self.conv.sent_messages()))
        self.assertEqual(20, len((yield self.conv.sent_messages(
                                        include_sensitive=True))))

    @inlineCallbacks
    def test_sent_messages_include_sensitive_and_scrub(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20, helper_metadata={
            'go': {
                'sensitive': True,
            }})

        def scrubber(msg):
            msg['content'] = 'scrubbed'
            return msg

        scrubbed_messages = yield self.conv.sent_messages(
            include_sensitive=True, scrubber=scrubber)
        self.assertEqual(len(scrubbed_messages), 20)
        for message in scrubbed_messages:
            self.assertEqual(message['content'], 'scrubbed')

    @inlineCallbacks
    def test_sent_messages_dictionary(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        [msg] = yield self.store_outbound(batch_key, count=1)
        [sent_message] = yield self.conv.sent_messages()
        self.assertEqual(msg['message_id'], sent_message['message_id'])

    @inlineCallbacks
    def test_get_tags(self):
        yield self.conv.start()
        [tag] = yield self.conv.get_tags()
        self.assertEqual(tag, ('longcode', 'longcode10001'))

    @inlineCallbacks
    def test_get_progress_status(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
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
        batch_key = yield self.conv.get_latest_batch_key()
        outbound = yield self.store_outbound(batch_key, count=10)
        yield self.store_event(outbound, 'ack', count=8)
        self.assertEqual((yield self.conv.get_progress_percentage()), 80)

    @inlineCallbacks
    def test_acquire_tag(self):
        tag = yield self.conv.acquire_tag()
        self.assertEqual(tag, ('longcode', 'longcode10001'))

    @inlineCallbacks
    def test_acquire_tag_if_none_available(self):
        yield self._declare_tags(u"shortcode", count=0)
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
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20, time_multiplier=0)
        # 20 messages in 5 minutes = 4 messages per minute
        self.assertEqual(
            (yield self.conv.get_inbound_throughput()), 4)
        # 20 messages in 20 seconds = 60 messages per minute
        self.assertEqual(
            (yield self.conv.get_inbound_throughput(sample_time=20)), 60)

    @inlineCallbacks
    def test_get_outbound_throughput(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20, time_multiplier=0)
        # 20 messages in 5 minutes = 4 messages per minute
        self.assertEqual(
            (yield self.conv.get_outbound_throughput()), 4)
        # 20 messages in 20 seconds = 60 messages per minute
        self.assertEqual(
            (yield self.conv.get_outbound_throughput(sample_time=20)), 60)

    @inlineCallbacks
    def do_search(self, conv, direction, *args,
                                    **kwargs):
        batch_key = kwargs.get('batch_key',
                            (yield self.conv.get_latest_batch_key()))
        search_callback = {
            'inbound': conv.find_inbound_messages_matching,
            'outbound': conv.find_outbound_messages_matching,
        }[direction]

        results_callback = {
            'inbound': conv.get_inbound_messages_for_token,
            'outbound': conv.get_outbound_messages_for_token,
        }[direction]

        kwargs.update({'wait': True})
        token = yield search_callback(*args, **kwargs)
        messages = yield results_callback(token, batch_key=batch_key)
        returnValue(messages)

    @inlineCallbacks
    def test_find_inbound_messages_matching(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20)
        matching = yield self.do_search(self.conv, 'inbound', 'hello')
        self.assertEqual(len(matching), 20)
        matching = yield self.do_search(self.conv, 'inbound', 'hello world 1')
        self.assertEqual(len(matching), 11)
        matching = yield self.do_search(self.conv, 'inbound', 'hello world 1$')
        self.assertEqual(len(matching), 1)

    @inlineCallbacks
    def test_find_inbound_messages_matching_flags(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20)
        matching = yield self.do_search(self.conv, 'inbound', 'HELLO',
                                        flags="i")
        self.assertEqual(len(matching), 20)
        matching = yield self.do_search(self.conv, 'inbound', 'HELLO',
                                        flags="")
        self.assertEqual(len(matching), 0)

    @inlineCallbacks
    def test_find_inbound_messages_matching_flags_custom_key(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_inbound(batch_key, count=20)
        matching = yield self.do_search(self.conv, 'inbound', 'FROM',
                                        flags='i', key='msg.from_addr')
        self.assertEqual(len(matching), 20)
        matching = yield self.do_search(self.conv, 'inbound', 'FROM', flags='',
                                        key='msg.from_addr')
        self.assertEqual(len(matching), 0)

    @inlineCallbacks
    def test_find_outbound_messages_matching(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20)
        matching = yield self.do_search(self.conv, 'outbound', 'hello')
        self.assertEqual(len(matching), 20)
        matching = yield self.do_search(self.conv, 'outbound', 'hello world 1')
        self.assertEqual(len(matching), 11)
        matching = yield self.do_search(self.conv, 'outbound',
                                        'hello world 1$')
        self.assertEqual(len(matching), 1)

    @inlineCallbacks
    def test_find_outbound_messages_matching_flags(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20)
        matching = yield self.do_search(self.conv, 'outbound', 'HELLO',
                                        flags='i')
        self.assertEqual(len(matching), 20)
        matching = yield self.do_search(self.conv, 'outbound', 'HELLO',
                                        flags='')
        self.assertEqual(len(matching), 0)

    @inlineCallbacks
    def test_find_outbound_messages_matching_flags_custom_key(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20)
        matching = yield self.do_search(self.conv, 'outbound', 'TO', flags='i',
                                        key='msg.to_addr')
        self.assertEqual(len(matching), 20)
        matching = yield self.do_search(self.conv, 'outbound', 'TO', flags='',
                                        key='msg.to_addr')
        self.assertEqual(len(matching), 0)

    @inlineCallbacks
    def test_get_aggregate_keys(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20, time_multiplier=12)
        inbound_aggregate = yield self.conv.get_aggregate_keys('inbound')
        self.assertEqual(inbound_aggregate, [])
        outbound_aggregate = yield self.conv.get_aggregate_keys('outbound')
        bucket_keys = [bucket for bucket, _ in outbound_aggregate]
        buckets = [keys for _, keys in outbound_aggregate]
        self.assertEqual(bucket_keys,
            [datetime.now().date() - timedelta(days=i)
                for i in range(9, -1, -1)])
        for bucket in buckets:
            self.assertEqual(len(bucket), 2)

    @inlineCallbacks
    def test_get_aggregate_count(self):
        yield self.conv.start()
        batch_key = yield self.conv.get_latest_batch_key()
        yield self.store_outbound(batch_key, count=20, time_multiplier=12)
        inbound_aggregate = yield self.conv.get_aggregate_count('inbound')
        self.assertEqual(inbound_aggregate, [])
        outbound_aggregate = yield self.conv.get_aggregate_count('outbound')
        bucket_keys = [bucket for bucket, _ in outbound_aggregate]
        buckets = [keys for _, keys in outbound_aggregate]
        self.assertEqual(bucket_keys,
            [datetime.now().date() - timedelta(days=i)
                for i in range(9, -1, -1)])
        for bucket in buckets:
            self.assertEqual(bucket, 2)

    @inlineCallbacks
    def test_get_groups(self):
        groups = yield self.user_api.list_groups()
        self.assertEqual([], groups)
        group = yield self.user_api.contact_store.new_group(u'test group')
        self.conv.groups.add_key(group.key)
        [found_group] = yield self.conv.get_groups()
        self.assertEqual(found_group.key, group.key)
