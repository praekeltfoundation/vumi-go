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
