from vumi.tests.helpers import VumiTestCase

from go.vumitools.tests.helpers import VumiApiHelper
from go.vumitools.conversation.definition import ConversationDefinitionBase


class DummyConversationDefinition(ConversationDefinitionBase):
    def configured_endpoints(self, config):
        return config['endpoints']


class TestConversationDefinitionBase(VumiTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(VumiApiHelper(is_sync=True))
        self.user_helper = self.vumi_helper.get_or_create_user()
        self.user_api = self.user_helper.user_api
        self.conv = self.user_helper.create_conversation(u'jsbox')

    def mk_channel(self, name):
        self.vumi_helper.setup_tagpool(name, [name])
        self.user_helper.add_tagpool_permission(name)
        tag = self.user_api.acquire_tag(name)
        return self.user_api.get_channel(tag)

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

    def test_update_config(self):
        dfn = ConversationDefinitionBase(self.conv)
        config = {'endpoints': []}
        dfn.update_config(self.user_api, config)
        self.assertEqual(self.conv.config, config)

    def test_update_config_update_endpoints(self):
        dfn = DummyConversationDefinition(self.conv)
        self.conv.set_config({'endpoints': ['foo', 'bar']})
        dfn.update_config(self.user_api, {'endpoints': ['bar', 'baz']})
        self.assertEqual(self.conv.extra_endpoints, ['bar', 'baz'])

    def test_update_config_detach_removed_endpoints(self):
        user_account = self.user_api.get_user_account()
        rt = user_account.routing_table
        self.conv.set_config({'endpoints': ['foo', 'bar', 'baz']})

        chan1 = self.mk_channel(u'c1')
        chan2 = self.mk_channel(u'c2')
        chan3 = self.mk_channel(u'c3')
        chan4 = self.mk_channel(u'c4')
        conv_conn = self.conv.get_connector()

        rt.add_entry(chan1.get_connector(), 'default', conv_conn, 'foo')
        rt.add_entry(conv_conn, 'foo', chan2.get_connector(), 'default')
        rt.add_entry(chan3.get_connector(), 'default', conv_conn, 'bar')
        rt.add_entry(conv_conn, 'bar', chan4.get_connector(), 'default')

        rt.validate_all_entries()
        user_account.save()

        dfn = DummyConversationDefinition(self.conv)
        dfn.update_config(self.user_api, {'endpoints': ['bar']})

        user_account = self.user_api.get_user_account()
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
