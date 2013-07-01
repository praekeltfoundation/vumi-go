import json

from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.routing import views


class RoutingScreenTestCase(DjangoGoApplicationTestCase):
    # Most of the functionality of this view lives in JS, so we just test that
    # we're correctly injecting initial state into the template.

    def setUp(self):
        # Monkey patch _get_routing_table
        self._orig_get_routing_table = views._get_routing_table
        views._get_routing_table = self.get_routing_table

        super(RoutingScreenTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username=self.user.username, password='password')

    def tearDown(self):
        views._get_routing_table = self._orig_get_routing_table
        super(RoutingScreenTestCase, self).setUp()

    def get_routing_table(self, user_account_key, session_id):
        self.assertEqual(user_account_key, self.user_api.user_account_key)
        response = self.routing_table_api_response.copy()
        response['campaign_id'] = user_account_key
        return json.dumps(response)

    def make_routing_table(self, tags=(), conversations=(), routing=()):
        routing_table = {
            u'campaign_id': self.user_api.user_account_key,
            u'channels': [],
            u'conversations': [],
            u'routing_blocks': [],
            u'routing_entries': [],
        }

        for pool, tag in tags:
            routing_table[u'channels'].append({
                u'uuid': u'%s:%s' % (pool, tag),
                u'name': tag,
                u'tag': [pool, tag],
                u'description': u"%s: %s" % (
                    pool.replace('_', ' ').title(), tag),
                u'endpoints': [{
                    u'name': u'default',
                    u'uuid': u'TRANSPORT_TAG:%s:%s:default' % (pool, tag),
                }],
            })

        for conv in conversations:
            routing_table[u'conversations'].append({
                u'uuid': conv.key,
                u'type': conv.conversation_type,
                u'name': conv.name,
                u'description': conv.description,
                u'endpoints': [{
                    u'name': u'default',
                    u'uuid': u'CONVERSATION:%s:%s:default' % (
                        conv.conversation_type, conv.key),
                }],
            })

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
            routing_table[u'routing_entries'].append({
                u'source': {u'uuid': mkconn(src)},
                u'target': {u'uuid': mkconn(dst)},
            })

        return routing_table

    def test_empty_routing(self):
        self.routing_table_api_response = self.make_routing_table()
        response = self.client.get(reverse('routing'))
        model_data = response.context['model_data']
        self.assertEqual(
            self.routing_table_api_response, json.loads(model_data))
        self.assertContains(response, model_data)
        self.assertContains(response, reverse('channels:new_channel'))
        self.assertContains(
            response, reverse('conversations:new_conversation'))

    def test_non_empty_routing(self):
        tag = (u'pool', u'tag')
        self.routing_table_api_response = self.make_routing_table(
            tags=[tag], conversations=[self.conversation],
            routing=[(self.conversation, tag), (tag, self.conversation)])
        response = self.client.get(reverse('routing'))
        model_data = response.context['model_data']
        self.assertEqual(
            self.routing_table_api_response, json.loads(model_data))
        self.assertContains(response, model_data)
