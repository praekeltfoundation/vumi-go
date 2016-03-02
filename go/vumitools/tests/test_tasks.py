import go.base.utils
from go.conversation.view_definition import ConversationViewDefinitionBase
from go.vumitools.conversation.definition import ConversationDefinitionBase
from go.vumitools.metrics import ConversationMetric
from go.vumitools.tests.helpers import djangotest_imports
from go.vumitools.tasks import (
    get_and_reset_recent_conversations, publish_conversation_metrics)

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class DummyMetric(ConversationMetric):
    METRIC_NAME = 'dummy_metric'

    def get_value(self, user_api):
        return 42


class DummyConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'dummy'

    metrics = (DummyMetric,)


DUMMY_CONVERSATION_DEFS = {
    'dummy': (DummyConversationDefinition, ConversationViewDefinitionBase),
}


DUMMY_CONVERSATION_SETTINGS = dict([
    ('gotest.' + app, {
        'namespace': app,
        'display_name': defs[0].conversation_display_name,
    }) for app, defs in DUMMY_CONVERSATION_DEFS.items()])


class FakeConversationPackage(object):
    """Pretends to be a package containing modules and classes for an app.
    """
    def __init__(self, conversation_type):
        self.definition = self
        self.view_definition = self
        def_cls, vdef_cls = DUMMY_CONVERSATION_DEFS[conversation_type]
        self.ConversationDefinition = def_cls
        self.ConversationViewDefinition = vdef_cls


class TestMetricsTask(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper(), setup_vumi_api=False)
        self.monkey_patch(
            go.config, 'get_conversation_pkg', self._get_conversation_pkg)
        self.vumi_helper.patch_config(
            VUMI_INSTALLED_APPS=DUMMY_CONVERSATION_SETTINGS)
        self.vumi_helper.setup_vumi_api()
        self.redis = self.vumi_helper.get_redis_manager()
        self.user_helper = self.vumi_helper.make_django_user()

    def _get_conversation_pkg(self, conversation_type, from_list=()):
        """Test stub for `go.base.utils.get_conversation_pkg()`
        """
        return FakeConversationPackage(conversation_type)

    def make_conv(self, conv_name, conv_type=u'dummy', **kw):
        return self.user_helper.create_conversation(
            u'dummy', name=u'myconv', **kw)

    def test_get_conversation_metrics(self):
        conv = self.make_conv(u'my_conv')
        acc_key = conv.user_account.key
        conv_details = '{"account_key": "%s","conv_key": "%s"}' % \
            (acc_key, conv.key)

        # Add data to redis
        subredis = self.redis.sub_manager("conversation.metrics.middleware")
        subredis.sadd("recent_coversations", conv_details)

        [details] = get_and_reset_recent_conversations()

        # Check response and that redis sets are emtpy
        self.assertEqual(details, conv_details)
        self.assertIsNone(subredis.get("recent_conversations"))
        self.assertIsNone(subredis.get("old_recent_conversations"))

    def test_publish_conversation_metrics(self):
        conv = self.make_conv(u'my_conv')
        prefix = "go.campaigns.test-0-user.conversations.%s" % conv.key

        # Check that no messages have been sent
        self.assertEqual(self.vumi_helper.amqp_connection.get_metrics(), [])

        # Send the metrics
        publish_conversation_metrics(self.user_helper.user_api, conv)

        # Check that the correct metrics were sent
        [vumi_msg] = self.vumi_helper.amqp_connection.get_metrics()

        data = vumi_msg.payload['datapoints'][0]

        metric_name = data[0]
        self.assertEqual(metric_name, "%s.dummy_metric" % prefix)

        [values] = data[2]
        self.assertEqual(values[1], 42)
