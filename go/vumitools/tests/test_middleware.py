"""Tests for go.vumitools.middleware"""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.persist.txriak_manager import TxRiakManager
from vumi.persist.txredis_manager import TxRedisManager
from vumi.components.message_store import MessageStore
from vumi.message import TransportUserMessage
from vumi.middleware import TaggingMiddleware

from go.vumitools.account import AccountStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.middleware import (
    NormalizeMsisdnMiddleware, LookupAccountMiddleware, LookupBatchMiddleware,
    LookupConversationMiddleware, OptOutMiddleware)


class MiddlewareTestCase(TestCase):

    @inlineCallbacks
    def setUp(self):
        self.redis = yield TxRedisManager.from_config('FAKE_REDIS')
        self.mdb_prefix = 'test_message_store'
        self.default_config = {
            'redis': self.redis._client,
            'message_store': {
                'store_prefix': self.mdb_prefix,
            }
        }

        self.manager = TxRiakManager.from_config({
                'bucket_prefix': self.mdb_prefix})
        self.account_store = AccountStore(self.manager)
        self.message_store = MessageStore(self.manager, self.redis)

        self.account = yield self.account_store.new_user(u'user')
        self.conv_store = ConversationStore.from_user_account(self.account)
        self.tag = ('xmpp', 'test1@xmpp.org')

    @inlineCallbacks
    def tearDown(self):
        yield self.manager.purge_all()
        yield self.redis._close()
        yield super(MiddlewareTestCase, self).tearDown()

    @inlineCallbacks
    def create_conversation(self, conversation_type=u'bulk_message',
                            subject=u'subject', message=u'message'):
        conversation = yield self.conv_store.new_conversation(
            conversation_type, subject, message)
        returnValue(conversation)

    @inlineCallbacks
    def tag_conversation(self, conversation, tag):
        batch_id = yield self.message_store.batch_start([tag],
                            user_account=unicode(self.account.key))
        conversation.batches.add_key(batch_id)
        conversation.save()
        returnValue(batch_id)

    def create_middleware(self, middleware_class, name='dummy_middleware',
                            config=None):
        dummy_worker = object()
        mw = middleware_class(name, config or self.default_config,
                                dummy_worker)
        mw.setup_middleware()
        return mw

    def mk_msg(self, to_addr, from_addr):
        return TransportUserMessage(to_addr=to_addr, from_addr=from_addr,
                                   transport_name="dummy_endpoint",
                                   transport_type="dummy_transport_type")


class NormalizeMisdnMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(NormalizeMisdnMiddlewareTestCase, self).setUp()
        self.mw = self.create_middleware(NormalizeMsisdnMiddleware, config={
            'country_code': '256'
        })

    def test_normalization(self):
        msg = self.mk_msg(to_addr='8007', from_addr='256123456789')
        msg = self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['from_addr'], '+256123456789')


class LookupAccountMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(LookupAccountMiddlewareTestCase, self).setUp()
        conversation = yield self.create_conversation()
        yield self.tag_conversation(conversation, self.tag)
        self.mw = self.create_middleware(LookupAccountMiddleware)

    @inlineCallbacks
    def test_account_lookup(self):
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)
        yield self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['helper_metadata'], {
            'tag': {
                'tag': list(self.tag),
            },
            'go': {
                'user_account': self.account.key,
            }
        })


class LookupBatchMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(LookupBatchMiddlewareTestCase, self).setUp()
        self.mw = self.create_middleware(LookupBatchMiddleware)

    @inlineCallbacks
    def test_batch_lookup(self):
        conversation = yield self.create_conversation()
        batch_id = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)
        yield self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['helper_metadata'], {
            'go': {
                'batch_key': batch_id,
            },
            'tag': {
                'tag': list(self.tag),
            }
        })


class LookupConversationMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(LookupConversationMiddlewareTestCase, self).setUp()
        self.account_mw = self.create_middleware(LookupAccountMiddleware)
        self.batch_mw = self.create_middleware(LookupBatchMiddleware)
        self.conv_mw = self.create_middleware(LookupConversationMiddleware)

    @inlineCallbacks
    def test_conversation_lookup(self):
        conversation = yield self.create_conversation()
        batch_id = yield self.tag_conversation(conversation, self.tag)
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        TaggingMiddleware.add_tag_to_msg(msg, self.tag)
        yield self.account_mw.handle_inbound(msg, 'dummy_endpoint')
        yield self.batch_mw.handle_inbound(msg, 'dummy_endpoint')
        yield self.conv_mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['helper_metadata'], {
            'go': {
                'batch_key': batch_id,
                'user_account': self.account.key,
            },
            'tag': {
                'tag': list(self.tag),
            },
            'conversations': {
                'conversation_key': conversation.key,
                'conversation_type': conversation.conversation_type,
            }
        })


class OptOutMiddlewareTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(OptOutMiddlewareTestCase, self).setUp()
        self.config = self.default_config.copy()
        self.config.update({
            'keyword_separator': '-',
            'optout_keywords': ['STOP', 'HALT', 'QUIT']
        })
        self.mw = self.create_middleware(OptOutMiddleware, config=self.config)

    def send_keyword(self, mw, word, expected_response):
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        msg['content'] = '%s%sfoo' % (
            word, self.config['keyword_separator'])
        yield mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['helper_metadata'], expected_response)

    @inlineCallbacks
    def test_optout_flag(self):
        for keyword in self.config['optout_keywords']:
            yield self.send_keyword(self.mw, keyword, {
                'optout': {
                    'optout': True,
                    'optout_keyword': keyword.lower(),
                }
            })

    @inlineCallbacks
    def test_non_optout_keywords(self):
        for keyword in ['THESE', 'DO', 'NOT', 'OPT', 'OUT']:
            yield self.send_keyword(self.mw, keyword, {
                'optout': {
                    'optout': False,
                }
            })

    @inlineCallbacks
    def test_case_sensitivity(self):
        config = self.config.copy()
        config.update({
            'case_sensitive': True,
        })
        mw = self.create_middleware(OptOutMiddleware, config=config)

        yield self.send_keyword(mw, 'STOP', {
            'optout': {
                'optout': True,
                'optout_keyword': 'STOP',
            }
        })

        yield self.send_keyword(mw, 'stop', {
            'optout': {
                'optout': False,
            }
        })
