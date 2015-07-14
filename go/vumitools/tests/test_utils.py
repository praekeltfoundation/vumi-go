from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, MessageHelper

from go.vumitools.model_object_cache import ModelObjectCache
from go.vumitools.utils import (
    extract_auth_from_url, MessageMetadataDictHelper, MessageMetadataHelper)
from go.vumitools.tests.helpers import VumiApiHelper


class TestExtractAuthFromUrl(VumiTestCase):

    def test_extract_auth_from_url_no_auth(self):
        auth, url = extract_auth_from_url('http://go.vumi.org')
        self.assertEqual(auth, None)
        self.assertEqual(url, 'http://go.vumi.org')

    def test_extract_auth_from_url_with_auth(self):
        auth, url = extract_auth_from_url('http://u:p@go.vumi.org')
        self.assertEqual(auth, ('u', 'p'))
        self.assertEqual(url, 'http://go.vumi.org')

    def test_extract_auth_from_url_with_username(self):
        auth, url = extract_auth_from_url('http://u@go.vumi.org')
        self.assertEqual(auth, ('u', None))
        self.assertEqual(url, 'http://go.vumi.org')


class TestMessageMetadataDictHelper(VumiTestCase):

    def setUp(self):
        self.msg_helper = self.add_helper(MessageHelper())

    def mk_msg(self, go_metadata=None, optout_metadata=None):
        helper_metadata = {}
        if go_metadata is not None:
            helper_metadata['go'] = go_metadata
        if optout_metadata is not None:
            helper_metadata['optout'] = optout_metadata
        return self.msg_helper.make_inbound(
            "hi", helper_metadata=helper_metadata)

    def mk_md(self, message=None, go_metadata=None, optout_metadata=None):
        if message is None:
            message = self.mk_msg(go_metadata, optout_metadata)
        return MessageMetadataDictHelper(message['helper_metadata'])

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

    def test_get_conversation_key(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_conversation_key)
        md = self.mk_md(go_metadata={'conversation_key': 'conv-1'})
        self.assertEqual(md.get_conversation_key(), 'conv-1')

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

    def test_get_router_key(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_router_key)
        md = self.mk_md(go_metadata={'router_key': 'router-1'})
        self.assertEqual(md.get_router_key(), 'router-1')

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

    @inlineCallbacks
    def test_add_conversation_metadata(self):
        md = self.mk_md()
        self.assertEqual(md._go_metadata, {})

        vumi_helper = yield self.add_helper(VumiApiHelper())
        user_helper = yield vumi_helper.make_user(u'user')

        conv = yield user_helper.create_conversation(u'bulk_message')
        md.add_conversation_metadata(conv)

        self.assertEqual(md._go_metadata, {
            'user_account': user_helper.account_key,
            'conversation_type': conv.conversation_type,
            'conversation_key': conv.key,
        })

    @inlineCallbacks
    def test_add_router_metadata(self):
        md = self.mk_md()
        self.assertEqual(md._go_metadata, {})

        vumi_helper = yield self.add_helper(VumiApiHelper())
        user_helper = yield vumi_helper.make_user(u'user')

        router = yield user_helper.create_router(u'keyword')
        md.add_router_metadata(router)

        self.assertEqual(md._go_metadata, {
            'user_account': user_helper.account_key,
            'router_type': router.router_type,
            'router_key': router.key,
        })


class TestMessageMetadataHelper(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        self.msg_helper = self.add_helper(MessageHelper())

    def mk_msg(self, go_metadata=None, optout_metadata=None):
        helper_metadata = {}
        if go_metadata is not None:
            helper_metadata['go'] = go_metadata
        if optout_metadata is not None:
            helper_metadata['optout'] = optout_metadata
        return self.msg_helper.make_inbound(
            "hi", helper_metadata=helper_metadata)

    def mk_md(self, message=None, go_metadata=None, optout_metadata=None):
        if message is None:
            message = self.mk_msg(go_metadata, optout_metadata)
        return MessageMetadataHelper(self.vumi_helper.get_vumi_api(), message)

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
        md = self.mk_md(
            go_metadata={'user_account': self.user_helper.account_key})
        user_api = md.get_user_api()
        self.assertEqual(
            user_api.user_account_key, self.user_helper.account_key)

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
        conversation = yield self.user_helper.create_conversation(
            u'bulk_message')
        md = self.mk_md(go_metadata={
            'user_account': self.user_helper.account_key,
            'conversation_key': conversation.key,
        })
        md_conv = yield md.get_conversation()
        self.assertEqual(md_conv.key, conversation.key)

    @inlineCallbacks
    def test_get_conversation_with_cache(self):
        """
        If we're given a conversation cache, we fetch the conversation through
        that.
        """
        conv_cache = ModelObjectCache(reactor, 5)
        self.add_cleanup(conv_cache.cleanup)
        conversation = yield self.user_helper.create_conversation(
            u'bulk_message')
        msg = self.mk_msg(go_metadata={
            'user_account': self.user_helper.account_key,
            'conversation_key': conversation.key,
        })
        md = MessageMetadataHelper(
            self.vumi_helper.get_vumi_api(), msg,
            conversation_cache=conv_cache)

        self.assertEqual(conv_cache._models.keys(), [])
        md_conv = yield md.get_conversation()
        self.assertEqual(md_conv.key, conversation.key)
        self.assertEqual(conv_cache._models.keys(), [conversation.key])

    @inlineCallbacks
    def test_clear_object_cache(self):
        conversation = yield self.user_helper.create_conversation(
            u'bulk_message')
        md = self.mk_md(go_metadata={
            'user_account': conversation.user_account.key,
            'conversation_key': conversation.key,
        })
        md.set_tag(["pool", "tag"])
        self.assertEqual(md._store_objects, {})
        md_conv = yield md.get_conversation()
        self.assertEqual(md._store_objects, {
            'conversation': md_conv,
        })
        md.clear_object_cache()
        self.assertEqual(md._store_objects, {})

    @inlineCallbacks
    def test_conversation_caching(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_conversation)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertRaises(KeyError, md.get_conversation)
        conversation = yield self.user_helper.create_conversation(
            u'bulk_message')
        md = self.mk_md(go_metadata={
            'user_account': conversation.user_account.key,
            'conversation_key': conversation.key,
        })
        md_conv = yield md.get_conversation()
        self.assertEqual(md_conv.key, conversation.key)
        self.assertEqual(md_conv.status, conversation.status)

        # Modify the conversation and get it from md again, making sure we
        # still have cached data.
        conversation.set_status_starting()
        yield conversation.save()
        md_conv2 = yield md.get_conversation()
        self.assertIdentical(md_conv, md_conv2)
        self.assertNotEqual(md_conv2.status, conversation.status)

        # Clear the stored object cache and get the conversation from md again,
        # making sure we have new data now.
        md.clear_object_cache()
        md_conv3 = yield md.get_conversation()
        self.assertEqual(md_conv3.key, conversation.key)
        self.assertEqual(md_conv3.status, conversation.status)
        self.assertNotIdentical(md_conv, md_conv3)

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

    @inlineCallbacks
    def test_get_router(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_router)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertRaises(KeyError, md.get_router)
        router = yield self.user_helper.create_router(u'keyword')
        md = self.mk_md(go_metadata={
            'user_account': self.user_helper.account_key,
            'router_key': router.key,
        })
        md_router = yield md.get_router()
        self.assertEqual(md_router.key, router.key)

    @inlineCallbacks
    def test_router_caching(self):
        md = self.mk_md()
        self.assertRaises(KeyError, md.get_router)
        md = self.mk_md(go_metadata={'user_account': 'user-1'})
        self.assertRaises(KeyError, md.get_router)
        router = yield self.user_helper.create_router(u'keyword')
        md = self.mk_md(go_metadata={
            'user_account': router.user_account.key,
            'router_key': router.key,
        })
        md_router = yield md.get_router()
        self.assertEqual(md_router.key, router.key)
        self.assertEqual(md_router.status, router.status)

        # Modify the router and get it from md again, making sure we
        # still have cached data.
        router.set_status_starting()
        yield router.save()
        md_router2 = yield md.get_router()
        self.assertIdentical(md_router, md_router2)
        self.assertNotEqual(md_router2.status, router.status)

        # Clear the stored object cache and get the router from md again,
        # making sure we have new data now.
        md.clear_object_cache()
        md_router3 = yield md.get_router()
        self.assertEqual(md_router3.key, router.key)
        self.assertEqual(md_router3.status, router.status)
        self.assertNotIdentical(md_router, md_router3)

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

    def test_get_tagpool_metadata_no_tag(self):
        md = self.mk_md()
        self.assertEqual(None, md.tag)
        self.assertRaises(ValueError, md.get_tagpool_metadata)

    @inlineCallbacks
    def test_get_tagpool_metadata(self):
        yield self.vumi_helper.setup_tagpool("pool", ["tagname"], metadata={
            "foo": "bar",
        })
        md = self.mk_md()
        md.set_tag(["pool", "tagname"])

        tagpool_metadata = yield md.get_tagpool_metadata()
        self.assertEqual({"foo": "bar"}, tagpool_metadata)

    @inlineCallbacks
    def test_tagpool_metadata_caching(self):
        yield self.vumi_helper.setup_tagpool("pool", ["tagname"], metadata={
            "foo": "bar",
        })
        md = self.mk_md()
        md.set_tag(["pool", "tagname"])

        self.assertEqual({}, md._store_objects)
        tagpool_metadata = yield md.get_tagpool_metadata()
        self.assertEqual({"foo": "bar"}, tagpool_metadata)
        self.assertEqual(
            {'tagpool_metadata': tagpool_metadata}, md._store_objects)

        # Stash a fake thing in the cache to make sure that what we get is
        # actually the thing in the cache.
        md._store_objects['tagpool_metadata'] = "I am the cached metadata"
        cached_tagpool_metadata = yield md.get_tagpool_metadata()
        self.assertEqual(cached_tagpool_metadata, "I am the cached metadata")
