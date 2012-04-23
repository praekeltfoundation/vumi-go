# -*- test-case-name: go.vumitools.tests.test_middleware -*-
from vumi.middleware import TransportMiddleware
from vumi.utils import normalize_msisdn


class NormalizeMsisdnMiddleware(TransportMiddleware):

    def setup_middleware(self):
        self.country_code = self.config['country_code']

    def handle_inbound(self, message, endpoint):
        from_addr = normalize_msisdn(message.get('from_addr'),
                        country_code=self.country_code)
        message['from_addr'] = from_addr
        return message
