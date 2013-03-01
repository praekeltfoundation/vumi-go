from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.middleware.tagger import TaggingMiddleware

from go.vumitools.api import VumiApi
from go.vumitools.api_worker import OldGoMessageMetadata
from go.vumitools.tests.utils import GoPersistenceMixin


class OldGoMessageMetadataTestCase(GoPersistenceMixin, TestCase):
    use_riak = True

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()

        self.vumi_api = yield VumiApi.from_config_async(self._persist_config)
        self._persist_riak_managers.append(self.vumi_api.manager)
        self._persist_redis_managers.append(self.vumi_api.redis)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)
        self.tag = ('xmpp', 'test1@xmpp.org')

    def tearDown(self):
        return self._persist_tearDown()

    def create_conversation(self, conversation_type=u'bulk_message',
                            subject=u'subject', message=u'message'):
        return self.user_api.conversation_store.new_conversation(
            conversation_type, subject, message)

    @inlineCallbacks
    def tag_conversation(self, conversation, tag):
        batch_id = yield self.vumi_api.mdb.batch_start([tag],
                            user_account=unicode(self.account.key))
        conversation.batches.add_key(batch_id)
        conversation.save()
        returnValue(batch_id)

    def mk_msg(self, to_addr, from_addr):
        return TransportUserMessage(to_addr=to_addr, from_addr=from_addr,
                                   transport_name="dummy_endpoint",
                                   transport_type="dummy_transport_type")

    def mk_md(self, message):
        return OldGoMessageMetadata(self.vumi_api, message)

    @inlineCallbacks
    def test_account_key_lookup(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        account_key = yield md.get_account_key()
        self.assertEqual(account_key, self.account.key)
        self.assertEqual(msg['helper_metadata']['go'], {
                'batch_key': batch_key,
                'user_account': account_key,
                })

    @inlineCallbacks
    def test_batch_lookup(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        msg_batch_key = yield md.get_batch_key()
        self.assertEqual(batch_key, msg_batch_key)
        self.assertEqual(msg['helper_metadata']['go'],
                         {'batch_key': batch_key})

    @inlineCallbacks
    def test_conversation_lookup(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        conv_key, conv_type = yield md.get_conversation_info()
        self.assertEqual(conv_key, conversation.key)
        self.assertEqual(conv_type, conversation.conversation_type)
        self.assertEqual(msg['helper_metadata']['go'], {
                'batch_key': batch_key,
                'user_account': self.account.key,
                'conversation_key': conv_key,
                'conversation_type': conv_type,
                })

    @inlineCallbacks
    def test_rewrap(self):
        conversation = yield self.create_conversation()
        batch_key = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)

        self.assertEqual(msg['helper_metadata'],
                         {'tag': {'tag': list(self.tag)}})

        md = self.mk_md(msg)
        # The metadata wrapper creates the 'go' metadata
        self.assertEqual(msg['helper_metadata']['go'], {})

        msg_batch_key = yield md.get_batch_key()
        self.assertEqual(batch_key, msg_batch_key)
        self.assertEqual(msg['helper_metadata']['go'],
                         {'batch_key': batch_key})

        # We create a new wrapper around the same message object and make sure
        # the cached message store objects are still there in the new one.
        new_md = self.mk_md(msg)
        self.assertNotEqual(md, new_md)
        self.assertEqual(md._store_objects, new_md._store_objects)
        self.assertEqual(md._go_metadata, new_md._go_metadata)

        # We create a new wrapper around the a copy of the message object and
        # make sure the message store object cache is empty, but the metadata
        # remains.
        other_md = self.mk_md(msg.copy())
        self.assertNotEqual(md, other_md)
        self.assertEqual({}, other_md._store_objects)
        self.assertEqual(md._go_metadata, other_md._go_metadata)

    def test_is_sensitive(self):
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        self.assertFalse(self.mk_md(msg).is_sensitive())

        msg['helper_metadata'] = {
            'go': {
                'sensitive': True,
            }
        }
        self.assertTrue(self.mk_md(msg).is_sensitive())
