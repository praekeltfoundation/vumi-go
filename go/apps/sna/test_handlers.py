
class USSDOptOutHandlerTestCase(MiddlewareTestCase):

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
