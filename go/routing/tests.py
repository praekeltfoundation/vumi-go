import json

from django.core.urlresolvers import reverse

from mock import patch

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.api.go_api.api_types import (
    ChannelType, ConversationType, RoutingEntryType)


class RoutingScreenTestCase(DjangoGoApplicationTestCase):
    # TODO: Stop abusing DjangoGoApplicationTestCase for this.

    # Most of the functionality of this view lives in JS, so we just test that
    # we're correctly injecting initial state into the template.

    def get_routing_table(self, user_account_key, session_id):
        self.assertEqual(user_account_key, self.user_api.user_account_key)
        return self.routing_table_api_response

    def make_routing_table(self, tags=(), conversations=(), routing=()):
        routing_table = {
            u'campaign_id': self.user_api.user_account_key,
            u'channels': [],
            u'conversations': [],
            u'routing_blocks': [],
            u'routing_entries': [],
        }

        for tag in tags:
            routing_table[u'channels'].append(ChannelType.format_channel(tag))

        for conv in conversations:
            routing_table[u'conversations'].append(
                ConversationType.format_conversation(conv))
        # TODO: Routing blocks

        def mkconn(thing):
            if isinstance(thing, tuple):
                # It's a tuple, so assume it's a tag.
                return u'TRANSPORT_TAG:%s:%s:default' % thing
            else:
                # Assume it's a conversation.
                return u'CONVERSATION:%s:%s:default' % (
                    thing.conversation_type, thing.key)

        for src, dst in routing:
            routing_table[u'routing_entries'].append(
                RoutingEntryType.format_entry(mkconn(src), mkconn(dst)))

        return json.dumps(routing_table)

    @patch('go.routing.views._get_routing_table')
    def test_empty_routing(self, mock_routing):
        mock_routing.side_effect = self.get_routing_table
        self.routing_table_api_response = self.make_routing_table()
        response = self.client.get(reverse('routing'))
        model_data = response.context['model_data']
        self.assertEqual(self.routing_table_api_response, model_data)
        self.assertContains(response, model_data)
        self.assertContains(response, reverse('channels:new_channel'))
        self.assertContains(
            response, reverse('conversations:new_conversation'))

    @patch('go.routing.views._get_routing_table')
    def test_non_empty_routing(self, mock_routing):
        self.setup_conversation()
        mock_routing.side_effect = self.get_routing_table
        tag = (u'pool', u'tag')
        self.routing_table_api_response = self.make_routing_table(
            tags=[tag], conversations=[self.conversation],
            routing=[(self.conversation, tag), (tag, self.conversation)])
        response = self.client.get(reverse('routing'))
        model_data = response.context['model_data']
        self.assertEqual(self.routing_table_api_response, model_data)
        self.assertContains(response, model_data)
