import base64
from urllib import urlencode

from twisted.internet.defer import inlineCallbacks

from vumi.utils import http_request_full
from vumi import log

from go.vumitools.handler import EventHandler
from go.vumitools.api import VumiUserApi
from go.vumitools.api_worker import GoMessageMetadata

from vxpolls.manager import PollManager


class YoPaymentHandler(EventHandler):

    def get_user_api(self, account_key):
        return VumiUserApi(self.dispatcher.vumi_api, account_key)

    def setup_handler(self):
        self.username = self.config['username']
        self.password = self.config['password']
        self.url = self.config['url']
        self.method = self.config['method']
        self.amount = self.config['amount']
        self.reason = self.config['reason']
        self.pm_prefix = self.config['poll_manager_prefix']

        self.pm = PollManager(self.dispatcher.vumi_api.redis, self.pm_prefix)

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

        gmt = GoMessageMetadata(self.dispatcher.vumi_api, message)
        conv_key, conv_type = yield gmt.get_conversation_info()

        poll_id = 'poll-%s' % (conv_key,)
        poll_config = yield self.pm.get_config(poll_id)

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

