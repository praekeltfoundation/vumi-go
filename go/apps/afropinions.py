class YoPaymentHandler(object):

    def __init__(self, username='', password='', url='', method='POST',
                    amount=0, reason='', redis={},
                    poll_manager_prefix='vumigo.'):
        self.username = username
        self.password = password
        self.url = url
        self.method = method
        self.amount = amount
        self.reason = reason
        self.pm_prefix = poll_manager_prefix
        self.pm = PollManager(self.get_redis(redis), self.pm_prefix)

    def get_redis(self, config):
        return redis.Redis(**config)

    def teardown_handler(self):
        self.pm.stop()

    def get_auth_headers(self, username, password):
        credentials = base64.b64encode('%s:%s' % (username, password))
        return {
            'Authorization': 'Basic %s' % (credentials.strip(),)
        }

    @inlineCallbacks
    def handle_message(self, message):
        if not self.url:
            log.error('No URL configured for YoPaymentHandler')
            return

        if not message.get('content'):
            return

        helper = LookupConversationMiddleware.map_message_to_conversation_info
        conv_info = helper(message)
        conv_key, conv_type = conv_info

        poll_id = 'poll-%s' % (conv_key,)
        poll_config = self.pm.get_config(poll_id)

        content = message.get('content')
        if not content:
            log.error('No content, skipping')
            return

        if content != poll_config.get('survey_completed_response'):
            log.error("Survey hasn't been completed, continuing")
            return

        request_params = {
            'msisdn': message['to_addr'],
            'amount': self.amount,
            'reason': self.reason,
        }

        log.info('Sending %s to %s via HTTP %s' % (
            request_params,
            self.url,
            self.method,
            ))
        response = yield http_request_full(self.url,
            data=urlencode(request_params),
            headers=self.get_auth_headers(self.username, self.password),
            method=self.method)
        log.info('Received response: %s / %s' % (response.code,
            response.delivered_body,))

