import json

from django.core.urlresolvers import reverse

from go.base.tests.utils import (
    VumiGoDjangoTestCase, FakeRpcResponse, FakeServer)

from go.api.go_api.api_types import (
    ChannelType, ConversationType, RoutingEntryType)


class RoutingScreenTestCase(VumiGoDjangoTestCase):
    # Most of the functionality of this view lives in JS, so we just test that
    # we're correctly injecting initial state into the template.

    use_riak = True

    def setUp(self):
        super(RoutingScreenTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()
        self.go_api = FakeServer()

    def tearDown(self):
        super(RoutingScreenTestCase, self).tearDown()
        self.go_api.tear_down()

    def make_routing_table(self, channels=(), conversations=(), routing=()):
        routing_table = {
            u'campaign_id': self.user_api.user_account_key,
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
        [request] = self.go_api.get_requests()
        data = request['data']

        self.assertEqual(data['method'], 'routing_table')
        self.assertEqual(data['params'], [self.user_api.user_account_key])

    def test_empty_routing(self):
        routing_table = self.make_routing_table()

        self.go_api.set_response(FakeRpcResponse(result=routing_table))
        response = self.client.get(reverse('routing'))

        self.check_api_request()
        self.check_model_data(response, routing_table)
        self.assertContains(response, reverse('channels:new_channel'))
        self.assertContains(
            response, reverse('conversations:new_conversation'))

    def test_non_empty_routing(self):
        conv = self.create_conversation()
        tag = (u'pool', u'tag')
        routing_table = self.make_routing_table(
            channels=[self.user_api.get_channel(tag)], conversations=[conv],
            routing=[(conv, tag), (tag, conv)])

        self.go_api.set_response(FakeRpcResponse(result=routing_table))
        response = self.client.get(reverse('routing'))

        self.check_api_request()
        self.check_model_data(response, routing_table)
        self.assertContains(response, reverse('channels:new_channel'))
        self.assertContains(
            response, reverse('conversations:new_conversation'))
