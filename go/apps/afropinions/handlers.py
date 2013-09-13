# -*- test-case-name: go.apps.afropinions.test_handlers -*-
import base64
from urllib import urlencode

from twisted.internet.defer import inlineCallbacks

from vumi.utils import http_request_full
from vumi import log

from go.vumitools.handler import EventHandler


class YoPaymentHandler(EventHandler):

    def setup_handler(self):
        self.username = self.config['username']
        self.password = self.config['password']
        self.url = self.config['url']
        self.method = self.config.get('method', 'POST')
        self.amount = self.config['amount']
        self.reason = self.config['reason']

    def get_auth_headers(self, username, password):
        credentials = base64.b64encode('%s:%s' % (username, password))
        return {
            'Authorization': 'Basic %s' % (credentials.strip(),)
        }

    @inlineCallbacks
    def handle_event(self, event, handler_config):
        """

        Hit the Yo payment gateway when a vxpoll is completed.

        Expects 'content' to be a dict with the following keys and values:

        :param from_addr:
            The address from which the message was received and which
            should be topped up with airtime.

        """

        participant = event['content']['participant']
        interactions = int(participant['interactions'])
        amount = interactions * int(self.amount)
        request_params = {
            'msisdn': event['content']['from_addr'],
            'amount': amount,
            'reason': self.reason,
        }

        headers = self.get_auth_headers(self.username, self.password)
        headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            })

        log.info('Sending %s to %s via HTTP %s' % (
            request_params,
            self.url,
            self.method,
            ))
        response = yield http_request_full(self.url,
            data=urlencode(request_params),
            headers=headers,
            method=self.method)
        log.info('Received response: %s / %s' % (response.code,
            response.delivered_body,))
