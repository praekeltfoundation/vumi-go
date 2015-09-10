import json

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse

    from go.api.go_api.tests.utils import MockRpc
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.api.go_api.api_types import (
        ChannelType, ConversationType, RoutingEntryType)


class TestRoutingScreen(GoDjangoTestCase):
    # Most of the functionality of this view lives in JS, so we just test that
    # we're correctly injecting initial state into the template.

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()
        self.mock_rpc = MockRpc()
        self.add_cleanup(self.mock_rpc.tearDown)

    def make_routing_table(self, channels=(), conversations=(), routing=()):
        routing_table = {
            u'campaign_id': self.user_helper.account_key,
            u'channels': [],
            u'conversations': [],
            u'routers': [],
            u'routing_entries': [],
        }

        for channel in channels:
            routing_table[u'channels'].append(
                ChannelType.format_channel(channel))

        for conv in conversations:
            routing_table[u'conversations'].append(
                ConversationType.format_conversation(conv))

        # TODO: routers

        def mkconn(thing):
            if isinstance(thing, tuple):
                # It's a tuple, so assume it's a tag.
                return u'TRANSPORT_TAG:%s:%s' % thing
            else:
                # Assume it's a conversation.
                return u'CONVERSATION:%s:%s' % (
                    thing.conversation_type, thing.key)

        for src, dst in routing:
            routing_table[u'routing_entries'].append(
                RoutingEntryType.format_entry(
                    (mkconn(src), 'default'), (mkconn(dst), 'default')))
        return routing_table

    def check_model_data(self, response, routing_table):
        model_data = response.context['model_data']

        self.assertEqual(
            json.loads(model_data),
            json.loads(json.dumps(routing_table)))

        self.assertContains(response, model_data)

    def check_api_request(self):
        request = self.mock_rpc.request
        self.assertEqual(request['method'], 'routing_table')
        self.assertEqual(request['params'], [self.user_helper.account_key])

    def test_empty_routing(self):
        routing_table = self.make_routing_table()

        self.mock_rpc.set_response(result=routing_table)
        response = self.client.get(reverse('routing'))

        self.check_api_request()
        self.check_model_data(response, routing_table)
        self.assertContains(response, reverse('channels:new_channel'))
        self.assertContains(
            response, reverse('conversations:new_conversation'))

    def test_non_empty_routing(self):
        conv = self.user_helper.create_conversation(u'bulk_message')
        tag = (u'pool', u'tag')
        routing_table = self.make_routing_table(
            channels=[self.user_helper.user_api.get_channel(tag)],
            conversations=[conv], routing=[(conv, tag), (tag, conv)])

        self.mock_rpc.set_response(result=routing_table)
        response = self.client.get(reverse('routing'))

        self.check_api_request()
        self.check_model_data(response, routing_table)
        self.assertContains(response, reverse('channels:new_channel'))
        self.assertContains(
            response, reverse('conversations:new_conversation'))
