"""Tests for go.api.go_api.api_types"""

from vumi.rpc import RpcCheckError
from vumi.tests.helpers import VumiTestCase

from go.api.go_api.api_types import (
    CampaignType, EndpointType, ConversationType, ChannelType,
    RouterType, RoutingEntryType, RoutingType)


class BaseTypeTestCase(VumiTestCase):
    DEFAULTS = {}

    def mk_dict(self, without=(), **kw):
        value = self.DEFAULTS.copy()
        value.update(kw)
        for key in without:
            del value[key]
        return value

    def basic_checks(self, check_type):
        check_type.check('name', self.mk_dict())
        for key in self.DEFAULTS:
            self.assertRaises(
                RpcCheckError, check_type.check, 'name',
                self.mk_dict(without=(key,)))


class TestCampaignType(BaseTypeTestCase):
    DEFAULTS = {
        u'key': u'campaign-1',
        u'name': u'Campaign One',
    }

    def test_basic_checks(self):
        self.basic_checks(CampaignType())


class TestEndpointType(BaseTypeTestCase):
    DEFAULTS = {
        u'uuid': u'endpoint-1',
        u'name': u'Endpoint 1',
    }

    def test_basic_checks(self):
        self.basic_checks(EndpointType())

    def test_format_uuid(self):
        uuid = EndpointType.format_uuid('foo', 'bar')
        self.assertEqual(uuid, u'foo::bar')

    def test_parse_uuid(self):
        self.assertEqual(EndpointType.parse_uuid('foo::bar::baz'),
                         ('foo::bar', 'baz'))


class TestConversationType(BaseTypeTestCase):
    DEFAULTS = {
        u'uuid': u'conv-1',
        u'type': u'jsbox',
        u'name': u'Conversation One',
        u'description': u'A Dummy Conversation',
        u'endpoints': [
            {u'uuid': u'endpoint-uuid-1', u'name': u'default'}
        ],
    }

    def test_basic_checks(self):
        self.basic_checks(ConversationType())


class TestChannelType(BaseTypeTestCase):
    DEFAULTS = {
        u'uuid': u'channel-1',
        u'tag': [u'apposit_sms', u'*121#'],
        u'name': u'*121#',
        u'description': u'Apposit Sms: *121#',
        u'endpoints': [
            {u'uuid': u'endpoint-uuid-1', u'name': u'default'}
        ],
    }

    def test_basic_checks(self):
        self.basic_checks(ChannelType())


class TestRouterType(BaseTypeTestCase):
    DEFAULTS = {
        u'uuid': u'router-uuid-1',
        u'type': u'keyword',
        u'name': u'keyword-router',
        u'description': u'Keyword',
        u'channel_endpoints': [
            {u'uuid': u'endpoint-uuid-2', u'name': u'default'}
        ],
        u'conversation_endpoints': [
            {u'uuid': u'endpoint-uuid-3', u'name': u'default'}
        ],
    }

    def test_basic_checks(self):
        self.basic_checks(RouterType())


class TestRoutingEntryType(BaseTypeTestCase):
    DEFAULTS = {
        u'source': {u'uuid': u'endpoint-uuid-1'},
        u'target': {u'uuid': u'endpoint-uuid-2'},
    }

    def test_basic_checks(self):
        self.basic_checks(RoutingEntryType())


class TestRoutingType(BaseTypeTestCase):
    DEFAULTS = {
        u'channels': [TestChannelType.DEFAULTS],
        u'routers': [TestRouterType.DEFAULTS],
        u'conversations': [TestConversationType.DEFAULTS],
        u'routing_entries': [TestRoutingEntryType.DEFAULTS],
    }

    def test_basic_checks(self):
        self.basic_checks(RoutingType())
