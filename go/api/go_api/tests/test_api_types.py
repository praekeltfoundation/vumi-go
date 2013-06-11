"""Tests for go.api.go_api.api_types"""

from twisted.trial.unittest import TestCase

from vumi.rpc import RpcCheckError

from go.api.go_api.api_types import (
    ConversationType, CampaignType)


class ConversationTypeTestCase(TestCase):

    def _conv_dict(self, without=(), **kw):
        conv_dict = kw.copy()
        conv_dict.setdefault('key', u'conv-1')
        conv_dict.setdefault('name', u'Conversation One')
        conv_dict.setdefault('description', u'A Dummy Conversation')
        conv_dict.setdefault('conversation_type', u'jsbox')
        for key in without:
            del conv_dict[key]
        return conv_dict

    def test_check(self):
        conv_type = ConversationType()
        conv_type.check('name', self._conv_dict())
        for key in ['key', 'name', 'description', 'conversation_type']:
            self.assertRaises(
                RpcCheckError, conv_type.check, 'name',
                self._conv_dict(without=(key,)))


class CampaignTypeTestCase(TestCase):
    def _campaign_dict(self, without=(), **kw):
        campaign_dict = kw.copy()
        campaign_dict.setdefault('key', u'campaign-1')
        campaign_dict.setdefault('name', u'Campaign One')
        for key in without:
            del campaign_dict[key]
        return campaign_dict

    def test_check(self):
        campaign_type = CampaignType()
        campaign_type.check('name', self._campaign_dict())
        for key in ['key', 'name']:
            self.assertRaises(
                RpcCheckError, campaign_type.check, 'name',
                self._campaign_dict(without=(key,)))
