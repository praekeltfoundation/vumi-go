from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import VumiTestCase

from go.vumitools.tests.helpers import VumiApiHelper
from go.vumitools.conversation.definition import ConversationDefinitionBase


class DummyConversationDefinition(ConversationDefinitionBase):
    def configured_endpoints(self, config):
        return config['endpoints']


class TestConversationDefinitionBase(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.get_or_create_user()
        self.user_api = self.user_helper.user_api
        self.conv = yield self.user_helper.create_conversation(u'jsbox')

    @inlineCallbacks
    def mk_channel(self, name):
        yield self.vumi_helper.setup_tagpool(name, [name])
        yield self.user_helper.add_tagpool_permission(name)
        tag = yield self.user_api.acquire_tag(name)
        channel = yield self.user_api.get_channel(tag)
        returnValue(channel)

    def test_get_endpoints(self):
        dfn = DummyConversationDefinition(self.conv)
        self.assertEqual(
            dfn.get_endpoints({'endpoints': ['foo', 'bar']}),
            ['foo', 'bar'])

    def test_get_endpoints_extra_endpoints(self):
        class ConversationDefinition(DummyConversationDefinition):
            extra_static_endpoints = ('foo', 'bar')

        dfn = ConversationDefinition(self.conv)
        self.assertEqual(
            dfn.get_endpoints({'endpoints': ['baz', 'quux']}),
            ['foo', 'bar', 'baz', 'quux'])

    @inlineCallbacks
    def test_update_config(self):
        user_account = yield self.user_api.get_user_account()

        dfn = ConversationDefinitionBase(self.conv)
        config = {'endpoints': []}

        yield dfn.update_config(user_account, config)
        self.assertEqual(self.conv.config, config)

    @inlineCallbacks
    def test_update_config_update_endpoints(self):
        user_account = yield self.user_api.get_user_account()

        dfn = DummyConversationDefinition(self.conv)
        self.conv.set_config({'endpoints': ['foo', 'bar']})

        yield dfn.update_config(user_account, {'endpoints': ['bar', 'baz']})
        self.assertEqual(self.conv.extra_endpoints, ['bar', 'baz'])

    @inlineCallbacks
    def test_update_config_detach_removed_endpoints(self):
        user_account = yield self.user_api.get_user_account()
        rt = user_account.routing_table
        self.conv.set_config({'endpoints': ['foo', 'bar', 'baz']})

        chan1 = yield self.mk_channel(u'c1')
        chan2 = yield self.mk_channel(u'c2')
        chan3 = yield self.mk_channel(u'c3')
        chan4 = yield self.mk_channel(u'c4')
        conv_conn = self.conv.get_connector()

        rt.add_entry(chan1.get_connector(), 'default', conv_conn, 'foo')
        rt.add_entry(conv_conn, 'foo', chan2.get_connector(), 'default')
        rt.add_entry(chan3.get_connector(), 'default', conv_conn, 'bar')
        rt.add_entry(conv_conn, 'bar', chan4.get_connector(), 'default')

        rt.validate_all_entries()
        yield user_account.save()

        dfn = DummyConversationDefinition(self.conv)
        yield dfn.update_config(user_account, {'endpoints': ['bar']})

        user_account = yield self.user_api.get_user_account()
        rt = user_account.routing_table

        self.assertEqual(rt.lookup_source(conv_conn, 'foo'), None)
        self.assertEqual(rt.lookup_target(conv_conn, 'foo'), None)

        self.assertEqual(
            rt.lookup_source(conv_conn, 'bar'),
            [chan3.get_connector(), 'default'])

        self.assertEqual(
            rt.lookup_target(conv_conn, 'bar'),
            [chan4.get_connector(), 'default'])

        self.assertEqual(rt.lookup_target(conv_conn, 'baz'), None)
        self.assertEqual(rt.lookup_source(conv_conn, 'baz'), None)
