"""Tests for go.vumitools.middleware"""

from twisted.trial.unittest import TestCase

from go.vumitools.middleware import NormalizeMsisdnMiddleware
from vumi.message import TransportUserMessage


class NormalizeMisdnMiddlewareTestCase(TestCase):

    def setUp(self):
        dummy_worker = object()
        self.mw = NormalizeMsisdnMiddleware('dummy_middleware', {
            'country_code': '256'
        }, dummy_worker)
        self.mw.setup_middleware()

    def mk_msg(self, to_addr, from_addr):
        return TransportUserMessage(to_addr=to_addr, from_addr=from_addr,
                                   transport_name="dummy_endpoint",
                                   transport_type="dummy_transport_type")

    def test_normalization(self):
        msg = self.mk_msg(to_addr='8007', from_addr='256123456789')
        msg = self.mw.handle_inbound(msg, 'dummy_endpoint')
        self.assertEqual(msg['from_addr'], '+256123456789')
