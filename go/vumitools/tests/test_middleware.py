"""Tests for go.vumitools.middleware"""

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportUserMessage

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.middleware import NormalizeMsisdnMiddleware, OptOutMiddleware


class MiddlewareTestCase(AppWorkerTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(MiddlewareTestCase, self).setUp()
        self.default_config = self.mk_config({})

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


class YoPaymentHandlerTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(YoPaymentHandlerTestCase, self).setUp()
        self.config = self.default_config.copy()
        self.config.update({
            'accounts': {
                'account_key': [
                    {'yo': 'go.vumitools.middleware.YoPaymentHandler'},
                ],
            },
            'yo': {
                'username': 'username',
                'password': 'password',
                'url': 'http://some-host/',
                'amount': 1,
                'reason': 'testing',
            }
        })
        self.mw = self.create_middleware(PerAccountLogicMiddleware,
            config=self.config)

    def tearDown(self):
        self.mw.teardown_middleware()

    @inlineCallbacks
    def test_hitting_url(self):
        msg = self.mk_msg('to@domain.org', 'from@domain.org')
        msg['helper_metadata'] = {
            'go': {
                'user_account': 'account_key',
            },
            'conversations': {
                'conversation_key': 'b525588ddca74ffca30dbd921d37cf9e',
                'conversation_type': 'survey',
            }
        }
        # with LogCatcher() as log:
        yield self.mw.handle_outbound(msg, 'dummy_endpoint')
        # [error] = log.errors
        # self.assertTrue('No URL configured' in error['message'][0])

    def test_auth_headers(self):
        handler = self.mw.accounts['account_key'][0]
        auth = handler.get_auth_headers('username', 'password')
        credentials = base64.b64encode('username:password')
        self.assertEqual(auth, {
            'Authorization': 'Basic %s' % (credentials.strip(),)
            })


class SNAUSSDOptOutHandlerTestCase(MiddlewareTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(SNAUSSDOptOutHandlerTestCase, self).setUp()
        self.patch(SNAUSSDOptOutHandler, 'get_redis', lambda *a: self.r_server)
        self.config = self.default_config.copy()
        self.config.update({
            'accounts': {
                self.account.key: [
                    {'sna': 'go.vumitools.middleware.SNAUSSDOptOutHandler'},
                ],
            },
            'sna': {
                'account_key': self.account.key,
                'riak': {
                    'bucket_prefix': self.mdb_prefix,
                },
            }
        })
        self.mw = self.create_middleware(PerAccountLogicMiddleware,
            config=self.config)
        self.oo_store = OptOutStore(self.manager, self.account.key)
        self.pm = PollManager(self.r_server, 'vumigo.')

    def tearDown(self):
        self.mw.teardown_middleware()
        self.pm.stop()

    @inlineCallbacks
    def test_opt_in(self):
        msisdn = u'+2345'
        msg = self.mk_msg(msisdn, '1234')
        msg['helper_metadata'] = {
            'go': {
                'user_account': self.account.key,
            },
            'conversations': {
                'conversation_key': '1',
                'conversation_type': 'survey',
            }
        }

        yield self.oo_store.new_opt_out('msisdn', msisdn, {
            'message_id': unicode(msg['message_id'])})

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u'1'
        yield contact.save()

        [opt_out] = yield self.oo_store.list_opt_outs()
        self.assertTrue(opt_out)

        yield self.mw.handle_outbound(msg, 'dummy_endpoint')

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

    @inlineCallbacks
    def test_opt_out(self):
        msisdn = u'+2345'
        msg = self.mk_msg(msisdn, '1234')
        msg['helper_metadata'] = {
            'go': {
                'user_account': self.account.key,
            },
            'conversations': {
                'conversation_key': '1',
                'conversation_type': 'survey',
            }
        }

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u'2'
        yield contact.save()

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

        # It's not unicode because it hasn't been encoded & decoded
        # through JSON
        msg['message_id'] = unicode(msg['message_id'])
        yield self.mw.handle_outbound(msg, 'dummy_endpoint')

        [opt_out] = yield self.oo_store.list_opt_outs()
        self.assertTrue(opt_out)
