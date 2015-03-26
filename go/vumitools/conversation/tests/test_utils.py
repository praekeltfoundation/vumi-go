from datetime import datetime

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import VumiTestCase

from go.vumitools.opt_out import OptOutStore
from go.vumitools.tests.helpers import VumiApiHelper
from go.vumitools.tests.helpers import GoMessageHelper


class TestConversationWrapper(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'username')
        self.msg_helper = self.add_helper(
            GoMessageHelper(vumi_helper=self.vumi_helper))

        self.conv = yield self.user_helper.create_conversation(u'dummy')
        yield self.vumi_helper.setup_tagpool(
            u"pool", [u"tag%s" % (i,) for i in range(1, 5)], metadata={
                "display_name": "pool",
                "delivery_class": "sms",
                "transport_type": "sms",
                "transport_name": self.msg_helper.transport_name,
            })
        yield self.user_helper.add_tagpool_permission(u"pool")

    @inlineCallbacks
    def store_events(self, outbound, event_type, count=None, **kwargs):
        count = count or len(outbound)
        messages = outbound[0:count]
        events = []
        for message in messages:
            event_maker = getattr(self.msg_helper, 'make_%s' % (event_type,))
            event = event_maker(message, **kwargs)
            yield self.msg_helper.store_event(event)
            events.append(event)
        returnValue(events)

    @inlineCallbacks
    def add_channels_to_conversation(self, conv, *channel_tags):
        for tag in channel_tags:
            yield self.user_helper.user_api.acquire_specific_tag(tag)
        user_account = yield self.user_helper.get_user_account()
        for tag in channel_tags:
            channel = yield self.user_helper.user_api.get_channel(tag)
            user_account.routing_table.add_entry(
                conv.get_connector(), 'default',
                channel.get_connector(), 'default')
            user_account.routing_table.add_entry(
                channel.get_connector(), 'default',
                conv.get_connector(), 'default')
        yield user_account.save()

    @inlineCallbacks
    def test_count_inbound_messages(self):
        # XXX: Does this test make sense at all?
        yield self.conv.start()
        yield self.msg_helper.add_inbound_to_conv(self.conv, 5)
        self.assertEqual((yield self.conv.count_inbound_messages()), 5)

    @inlineCallbacks
    def test_count_outbound_messages(self):
        yield self.conv.start()
        yield self.msg_helper.add_outbound_to_conv(self.conv, 5)
        self.assertEqual((yield self.conv.count_outbound_messages()), 5)

    @inlineCallbacks
    def test_count_inbound_uniques(self):
        # TODO fix once we support uniques properly again
        yield self.conv.start()
        yield self.msg_helper.add_inbound_to_conv(self.conv, 3)
        self.assertEqual((yield self.conv.count_inbound_uniques()), 3)
        yield self.msg_helper.add_inbound_to_conv(self.conv, 4)
        self.assertEqual((yield self.conv.count_inbound_uniques()), 4)
        yield self.msg_helper.add_inbound_to_conv(self.conv, 2)
        self.assertEqual((yield self.conv.count_inbound_uniques()), 4)

    @inlineCallbacks
    def test_count_outbound_uniques(self):
        # TODO fix once we support uniques properly again
        yield self.conv.start()
        yield self.msg_helper.add_outbound_to_conv(self.conv, 3)
        self.assertEqual((yield self.conv.count_outbound_uniques()), 3)
        yield self.msg_helper.add_outbound_to_conv(self.conv, 4)
        self.assertEqual((yield self.conv.count_outbound_uniques()), 4)
        yield self.msg_helper.add_outbound_to_conv(self.conv, 2)
        self.assertEqual((yield self.conv.count_outbound_uniques()), 4)

    @inlineCallbacks
    def test_collect_messages(self):
        yield self.conv.start()
        created_msgs = yield self.msg_helper.add_inbound_to_conv(self.conv, 5)
        collected_msgs = yield self.conv.collect_messages(
            [msg['message_id'] for msg in created_msgs],
            self.conv.mdb.get_inbound_message,
            include_sensitive=False, scrubber=lambda msg: msg)
        self.assertEqual(
            [msg['message_id'] for msg in collected_msgs],
            [msg['message_id'] for msg in created_msgs])

    @inlineCallbacks
    def test_collect_messages_with_unknown_key(self):
        yield self.conv.start()
        created_msgs = yield self.msg_helper.add_inbound_to_conv(self.conv, 5)
        collected_msgs = yield self.conv.collect_messages(
            [msg['message_id'] for msg in created_msgs] + [u'unknown-key'],
            self.conv.mdb.get_inbound_message,
            include_sensitive=False, scrubber=lambda msg: msg)
        self.assertEqual(
            [msg['message_id'] for msg in collected_msgs],
            [msg['message_id'] for msg in created_msgs])

    @inlineCallbacks
    def test_received_messages(self):
        yield self.conv.start()
        yield self.msg_helper.add_inbound_to_conv(self.conv, 5)
        received_messages = yield self.conv.received_messages_in_cache()
        self.assertEqual(len(received_messages), 5)
        self.assertEqual(
            len((yield self.conv.received_messages_in_cache(0, 2))), 2)
        self.assertEqual(
            len((yield self.conv.received_messages_in_cache(2, 4))), 2)
        self.assertEqual(
            len((yield self.conv.received_messages_in_cache(5, 10))), 0)

    @inlineCallbacks
    def test_received_messages_preserve_ordering(self):
        yield self.conv.start()
        stored_messages = yield self.msg_helper.add_inbound_to_conv(
            self.conv, 5, start_date=datetime.now())
        sorted_stored_messages = sorted(
            stored_messages, key=lambda msg: msg['timestamp'], reverse=True)
        cached_messages = yield self.conv.received_messages_in_cache()
        self.assertEqual(
            [msg['message_id'] for msg in sorted_stored_messages],
            [msg['message_id'] for msg in cached_messages])

    @inlineCallbacks
    def test_received_messages_include_sensitive(self):
        yield self.conv.start()
        yield self.msg_helper.make_stored_inbound(
            self.conv, "hi", helper_metadata={
                'go': {'sensitive': True},
            })
        self.assertEqual([], (yield self.conv.received_messages_in_cache()))
        self.assertEqual(
            1,
            len((yield self.conv.received_messages_in_cache(
                include_sensitive=True))))

    @inlineCallbacks
    def test_received_messages_include_sensitive_and_scrub(self):
        yield self.conv.start()
        yield self.msg_helper.make_stored_inbound(
            self.conv, "hi", helper_metadata={
                'go': {'sensitive': True},
            })

        def scrubber(msg):
            msg['content'] = 'scrubbed'
            return msg

        [scrubbed_messages] = yield self.conv.received_messages_in_cache(
            include_sensitive=True, scrubber=scrubber)
        self.assertEqual(scrubbed_messages['content'], 'scrubbed')

    @inlineCallbacks
    def test_received_messages_dictionary(self):
        yield self.conv.start()
        msg = yield self.msg_helper.make_stored_inbound(self.conv, "hi")
        [reply] = yield self.conv.received_messages_in_cache()
        self.assertEqual(msg['message_id'], reply['message_id'])

    @inlineCallbacks
    def test_sent_messages(self):
        yield self.conv.start()
        yield self.msg_helper.add_outbound_to_conv(self.conv, 5)
        sent_messages = yield self.conv.sent_messages_in_cache()
        self.assertEqual(len(sent_messages), 5)
        self.assertEqual(
            len((yield self.conv.sent_messages_in_cache(0, 2))), 2)
        self.assertEqual(
            len((yield self.conv.sent_messages_in_cache(2, 4))), 2)
        self.assertEqual(
            len((yield self.conv.sent_messages_in_cache(5, 10))), 0)

    @inlineCallbacks
    def test_sent_messages_preserve_ordering(self):
        yield self.conv.start()
        stored_messages = yield self.msg_helper.add_outbound_to_conv(
            self.conv, 5, start_date=datetime.now())
        sorted_stored_messages = sorted(
            stored_messages, key=lambda msg: msg['timestamp'], reverse=True)
        cached_messages = yield self.conv.sent_messages_in_cache()
        self.assertEqual(
            [msg['message_id'] for msg in sorted_stored_messages],
            [msg['message_id'] for msg in cached_messages])

    @inlineCallbacks
    def test_sent_messages_include_sensitive(self):
        yield self.conv.start()
        yield self.msg_helper.make_stored_outbound(
            self.conv, "hi", helper_metadata={
                'go': {'sensitive': True},
            })
        self.assertEqual([], (yield self.conv.sent_messages_in_cache()))
        self.assertEqual(
            1,
            len((yield self.conv.sent_messages_in_cache(
                include_sensitive=True))))

    @inlineCallbacks
    def test_sent_messages_include_sensitive_and_scrub(self):
        yield self.conv.start()
        yield self.msg_helper.make_stored_outbound(
            self.conv, "hi", helper_metadata={
                'go': {'sensitive': True},
            })

        def scrubber(msg):
            msg['content'] = 'scrubbed'
            return msg

        [scrubbed_message] = yield self.conv.sent_messages_in_cache(
            include_sensitive=True, scrubber=scrubber)
        self.assertEqual(scrubbed_message['content'], 'scrubbed')

    @inlineCallbacks
    def test_sent_messages_dictionary(self):
        yield self.conv.start()
        msg = yield self.msg_helper.make_stored_outbound(self.conv, "hi")
        [sent_message] = yield self.conv.sent_messages_in_cache()
        self.assertEqual(msg['message_id'], sent_message['message_id'])

    @inlineCallbacks
    def test_get_channels(self):
        yield self.conv.start()
        yield self.add_channels_to_conversation(
            self.conv, ("pool", "tag1"), ("pool", "tag2"))
        [chan1, chan2] = yield self.conv.get_channels()
        self.assertEqual(chan1.tag, "tag1")
        self.assertEqual(chan2.tag, "tag2")

    @inlineCallbacks
    def test_get_channels_with_no_channels(self):
        yield self.conv.start()
        self.assertEqual([], (yield self.conv.get_channels()))

    @inlineCallbacks
    def test_has_channel_supporting(self):
        yield self.conv.start()
        yield self.vumi_helper.setup_tagpool(u"pool1", [u"tag1"], metadata={
            "supports": {"foo": True, "bar": True}})
        yield self.vumi_helper.setup_tagpool(u"pool2", [u"tag1"], metadata={
            "supports": {"foo": True, "bar": False}})
        yield self.add_channels_to_conversation(
            self.conv, ("pool1", "tag1"), ("pool2", "tag1"))

        @inlineCallbacks
        def assert_has_channel_supporting(expected_value, **kw):
            self.assertEqual(
                expected_value, (yield self.conv.has_channel_supporting(**kw)))

        yield assert_has_channel_supporting(True, foo=True, bar=True)
        yield assert_has_channel_supporting(True, foo=True)
        yield assert_has_channel_supporting(False, foo=False)
        yield assert_has_channel_supporting(True, bar=True)
        yield assert_has_channel_supporting(True, bar=False)
        yield assert_has_channel_supporting(False, zoo=True)
        yield assert_has_channel_supporting(True, zoo=False)

    @inlineCallbacks
    def test_get_progress_status(self):
        yield self.conv.start()
        outbound = yield self.msg_helper.add_outbound_to_conv(self.conv, 10)
        yield self.store_events(outbound, 'ack', count=8)
        yield self.store_events(outbound, 'nack', count=2)
        yield self.store_events(outbound, 'delivery_report', count=4,
                                delivery_status='delivered')
        yield self.store_events(outbound, 'delivery_report', count=1,
                                delivery_status='failed')
        yield self.store_events(outbound, 'delivery_report', count=1,
                                delivery_status='pending')
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
    def test_get_opted_in_contact_address(self):
        """
        If we ask for the opted-in address of a contact that has a suitable
        address and isn't opted out, we get that address.
        """
        contact_store = self.user_helper.user_api.contact_store
        contact = yield contact_store.new_contact(msisdn=u"+27000000001")

        contact_addr = yield self.conv.get_opted_in_contact_address(
            contact, None)

        self.assertEqual(contact_addr, contact.msisdn)

    @inlineCallbacks
    def test_get_opted_in_contact_address_opted_out(self):
        """
        If we ask for the opted-in address of a contact that has a suitable
        address and is opted out, we get None.
        """
        contact_store = self.user_helper.user_api.contact_store
        user_account = yield self.user_helper.get_user_account()
        opt_out_store = OptOutStore.from_user_account(user_account)
        contact = yield contact_store.new_contact(msisdn=u"+27000000001")
        yield opt_out_store.new_opt_out(u"msisdn", contact.msisdn, {
            "message_id": u"some-message-id",
        })

        contact_addr = yield self.conv.get_opted_in_contact_address(
            contact, None)

        self.assertEqual(contact_addr, None)

    @inlineCallbacks
    def test_get_opted_in_contact_address_no_address(self):
        """
        If we ask for the opted-in address of a contact that doesn't have a
        suitable address, we get None.
        """
        contact_store = self.user_helper.user_api.contact_store
        contact = yield contact_store.new_contact(msisdn=u"+27000000001")

        contact_addr = yield self.conv.get_opted_in_contact_address(
            contact, "gtalk")

        self.assertEqual(contact_addr, None)

    @inlineCallbacks
    def test_get_opted_in_contact_bunches(self):
        contact_store = self.user_helper.user_api.contact_store
        user_account = yield self.user_helper.get_user_account()
        opt_out_store = OptOutStore.from_user_account(user_account)

        @inlineCallbacks
        def get_contacts():
            bunches = yield self.conv.get_opted_in_contact_bunches(
                self.conv.delivery_class)
            contacts = []
            for bunch in bunches:
                contacts.extend((yield bunch))
            returnValue([c.msisdn for c in contacts])

        self.assertEqual(
            [],
            (yield get_contacts()))

        group = yield contact_store.new_group(u'a group')
        self.conv.add_group(group)
        yield self.conv.save()

        contact1 = yield contact_store.new_contact(msisdn=u'+27000000001')
        contact1.add_to_group(group)
        yield contact1.save()

        contact2 = yield contact_store.new_contact(msisdn=u'+27000000002')
        contact2.add_to_group(group)
        yield contact2.save()

        yield group.save()

        self.assertEqual(
            set(['+27000000001', '+27000000002']),
            set((yield get_contacts())))

        yield opt_out_store.new_opt_out(u'msisdn', contact2.msisdn, {
            'message_id': u'some-message-id',
        })

        self.assertEqual(
            ['+27000000001'],
            (yield get_contacts()))

    @inlineCallbacks
    def test_get_inbound_throughput(self):
        yield self.conv.start()
        yield self.msg_helper.add_inbound_to_conv(
            self.conv, 20, time_multiplier=0)
        # 20 messages in 5 minutes = 4 messages per minute
        self.assertEqual(
            (yield self.conv.get_inbound_throughput()), 4)
        # 20 messages in 20 seconds = 60 messages per minute
        self.assertEqual(
            (yield self.conv.get_inbound_throughput(sample_time=20)), 60)

    @inlineCallbacks
    def test_get_outbound_throughput(self):
        yield self.conv.start()
        yield self.msg_helper.add_outbound_to_conv(
            self.conv, 20, time_multiplier=0)
        # 20 messages in 5 minutes = 4 messages per minute
        self.assertEqual(
            (yield self.conv.get_outbound_throughput()), 4)
        # 20 messages in 20 seconds = 60 messages per minute
        self.assertEqual(
            (yield self.conv.get_outbound_throughput(sample_time=20)), 60)

    @inlineCallbacks
    def test_get_groups(self):
        groups = yield self.user_helper.user_api.list_groups()
        self.assertEqual([], groups)
        group = yield self.user_helper.user_api.contact_store.new_group(
            u'test group')
        self.conv.groups.add_key(group.key)
        [found_group] = yield self.conv.get_groups()
        self.assertEqual(found_group.key, group.key)

    def test_set_go_helper_metadata(self):
        self.assertEqual(self.conv.set_go_helper_metadata(), {'go': {
            'user_account': self.conv.user_account.key,
            'conversation_type': self.conv.conversation_type,
            'conversation_key': self.conv.key,
        }})

    @inlineCallbacks
    def test_conversation_type_display_name(self):
        conv = yield self.user_helper.create_conversation(u'static_reply')
        self.assertEqual(
            conv.conversation_type_display_name, 'Static Reply')

    def test_conversation_type_display_name_fallback(self):
        self.assertEqual(
            self.conv.conversation_type_display_name, u'dummy')
