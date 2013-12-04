from twisted.trial.unittest import SkipTest
from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportUserMessage

from go.vumitools.utils import MessageMetadataHelper
from go.vumitools.tests.utils import GoTestCase


class MessageMetadataHelperTestCase(GoTestCase):
    use_riak = True

    @inlineCallbacks
    def setUp(self):
        super(MessageMetadataHelperTestCase, self).setUp()
        self.vumi_api = yield self.get_vumi_api()
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)

    def create_conversation(self, conversation_type=u'bulk_message',
                            name=u'name', description=u'desc', config={}):
        return self.user_api.new_conversation(
            conversation_type, name, description, config)

    def mk_msg(self, go_metadata=None, optout_metadata=None):
        helper_metadata = {}
        if go_metadata is not None:
            helper_metadata['go'] = go_metadata
        if optout_metadata is not None:
            helper_metadata['optout'] = optout_metadata
        return TransportUserMessage(
            to_addr="to@domain.org", from_addr="from@domain.org",
            transport_name="dummy_endpoint",
            transport_type="dummy_transport_type",
            helper_metadata=helper_metadata)

    def mk_md(self, message=None, go_metadata=None, optout_metadata=None):
        if message is None:
            message = self.mk_msg(go_metadata, optout_metadata)
        return MessageMetadataHelper(self.vumi_api, message)

    def test_is_sensitive(self):
        md = self.mk_md()
        self.assertFalse(md.is_sensitive())
        md = self.mk_md(go_metadata={'sensitive': True})
        self.assertTrue(md.is_sensitive())

    def test_has_user_account(self):
        md = self.mk_md()
        self.assertFalse(md.has_user_account())
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertTrue(md.has_user_account())

    def test_get_account_key(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_account_key)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertEqual(md.get_account_key(), 'user-1')

    def test_get_user_api(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_user_api)
        md = self.mk_md(go_metadata={
            'user_account': self.user_api.user_account_key})
        user_api = md.get_user_api()
        self.assertEqual(user_api.user_account_key,
                         self.user_api.user_account_key)

    def test_get_conversation_key(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_conversation_key)
        md = self.mk_md(go_metadata={'conversation_key': 'conv-1'})
        self.assertEqual(md.get_conversation_key(), 'conv-1')

    @inlineCallbacks
    def test_get_conversation(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_conversation)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertRaises(KeyError, md.get_conversation)
        conversation = yield self.create_conversation()
        md = self.mk_md(go_metadata={
            'user_account': self.user_api.user_account_key,
            'conversation_key': conversation.key,
        })
        md_conv = yield md.get_conversation()
        self.assertEqual(md_conv.key, conversation.key)

    @inlineCallbacks
    def test_conversation_caching(self):
        """
        Conversation objects are cached across calls to get_conversation() and
        clear_object_cache() clears this cache.
        """
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_conversation)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertRaises(KeyError, md.get_conversation)
        conversation = yield self.create_conversation()
        md = self.mk_md(go_metadata={
            'user_account': self.user_api.user_account_key,
            'conversation_key': conversation.key,
        })
        self.assertEqual(md._store_objects, {})
        md_conv = yield md.get_conversation()
        self.assertEqual(md_conv.key, conversation.key)
        self.assertEqual(md_conv.status, conversation.status)
        self.assertNotEqual(md._store_objects, {})

        # Modify the conversation and get it from md again, making sure we
        # still have cached data.
        conversation.set_status_starting()
        yield conversation.save()
        md_conv = yield md.get_conversation()
        self.assertEqual(md_conv.key, conversation.key)
        self.assertNotEqual(md_conv.status, conversation.status)

        # Clear the stored object cache and get the conversation from md again,
        # making sure we have new data now.
        self.assertNotEqual(md._store_objects, {})
        md.clear_object_cache()
        self.assertEqual(md._store_objects, {})
        md_conv = yield md.get_conversation()
        self.assertEqual(md_conv.key, conversation.key)
        self.assertEqual(md_conv.status, conversation.status)

    def test_get_conversation_info(self):
        md = self.mk_md()
        self.assertEqual(md.get_conversation_info(), None)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertEqual(md.get_conversation_info(), None)
        md = self.mk_md(go_metadata={
            'user_account': 'user-1',
            'conversation_type': 'dummy',
        })
        self.assertEqual(md.get_conversation_info(), None)
        md = self.mk_md(go_metadata={
            'user_account': 'user-1',
            'conversation_type': 'dummy',
            'conversation_key': 'conv-1',
        })
        self.assertEqual(md.get_conversation_info(), {
            'user_account': 'user-1',
            'conversation_type': 'dummy',
            'conversation_key': 'conv-1',
        })

    def test_set_conversation_info(self):
        msg = self.mk_msg()
        md = self.mk_md(msg)
        md.set_conversation_info('dummy', 'conv-1')
        self.assertEqual(msg['helper_metadata']['go'], {
            'conversation_type': 'dummy',
            'conversation_key': 'conv-1',
        })

    def test_set_user_account(self):
        msg = self.mk_msg()
        md = self.mk_md(msg)
        md.set_user_account('user-1')
        self.assertEqual(msg['helper_metadata']['go'], {
            'user_account': 'user-1',
        })

    def test_is_optout_message(self):
        md = self.mk_md()
        self.assertFalse(md.is_optout_message())
        md = self.mk_md(optout_metadata={"optout": True})
        self.assertTrue(md.is_optout_message())

    def test_get_router_key(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_router_key)
        md = self.mk_md(go_metadata={'router_key': 'router-1'})
        self.assertEqual(md.get_router_key(), 'router-1')

    def test_get_router(self):
        raise SkipTest("Add test once VumiUserApi has a get_router method")

    def test_get_router_info(self):
        md = self.mk_md()
        self.assertEqual(md.get_router_info(), None)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertEqual(md.get_router_info(), None)
        md = self.mk_md(go_metadata={
            'user_account': 'user-1',
            'router_type': 'dummy',
        })
        self.assertEqual(md.get_router_info(), None)
        md = self.mk_md(go_metadata={
            'user_account': 'user-1',
            'router_type': 'dummy',
            'router_key': 'router-1',
        })
        self.assertEqual(md.get_router_info(), {
            'user_account': 'user-1',
            'router_type': 'dummy',
            'router_key': 'router-1',
        })

    def test_set_router_info(self):
        msg = self.mk_msg()
        md = self.mk_md(msg)
        md.set_router_info('dummy', 'router-1')
        self.assertEqual(msg['helper_metadata']['go'], {
            'router_type': 'dummy',
            'router_key': 'router-1',
        })

    def test_set_tag(self):
        msg = self.mk_msg()
        md = self.mk_md(msg)
        md.set_tag(["pool", "tagname"])
        self.assertEqual(msg['helper_metadata']['tag'], {
            'tag': ["pool", "tagname"],
        })

    def test_rewrap(self):
        msg = self.mk_msg()

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        # We create a new wrapper around the same message object and make sure
        # the cached message store objects are still there in the new one.
        new_md = self.mk_md(msg)
        self.assertNotEqual(md, new_md)
        self.assertIdentical(md._store_objects, new_md._store_objects)
        self.assertIdentical(md._go_metadata, new_md._go_metadata)

        # We create a new wrapper around the a copy of the message object and
        # make sure the message store object cache is empty, but the metadata
        # remains.
        other_md = self.mk_md(msg.copy())
        self.assertNotIdentical(md, other_md)
        self.assertEqual({}, other_md._store_objects)
        self.assertEqual(md._go_metadata, other_md._go_metadata)
