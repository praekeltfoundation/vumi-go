from uuid import uuid4

from django.test.client import Client
from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase, declare_longcode_tags
from go.base import utils as base_utils
from go.channel.views import get_channel_view_definition


class ChannelViewsTestCase(VumiGoDjangoTestCase):

    def setUp(self):
        super(ChannelViewsTestCase, self).setUp()
        self.setup_api()
        declare_longcode_tags(self.api)
        self.user = self.mk_django_user()
        self.user_api = base_utils.vumi_api_for_user(self.user)
        self.add_tagpool_permission(u"longcode")

        self.client = Client()
        self.client.login(username=self.user.username, password='password')

    def add_tagpool_permission(self, tagpool, max_keys=None):
        permission = self.api.account_store.tag_permissions(
            uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        permission.save()
        account = self.user_api.get_user_account()
        account.tagpools.add(permission)
        account.save()

    def get_view_url(self, view, channel_key):
        view_def = get_channel_view_definition(None)
        return view_def.get_view_url(view, channel_key=channel_key)

    def test_get_new_channel(self):
        self.assertEqual(set([]), self.user_api.list_endpoints())
        response = self.client.get(reverse('channels:new_channel'))
        self.assertContains(response, 'International')
        self.assertContains(response, 'longcode:')

    def test_post_new_channel(self):
        self.assertEqual(set([]), self.user_api.list_endpoints())
        response = self.client.post(reverse('channels:new_channel'), {
            'country': 'International', 'channel': 'longcode:'})
        tag = (u'longcode', u'default10001')
        channel_key = u'%s:%s' % tag
        self.assertRedirects(response, self.get_view_url('show', channel_key))
        self.assertEqual(set([tag]), self.user_api.list_endpoints())

    def test_show_channel_missing(self):
        response = self.client.get(self.get_view_url('show', u'foo:bar'))
        self.assertEqual(response.status_code, 404)

    def test_show_channel(self):
        tag = (u'longcode', u'default10002')
        channel_key = u'%s:%s' % tag
        self.user_api.acquire_specific_tag(tag)
        response = self.client.get(self.get_view_url('show', channel_key))
        self.assertContains(response, tag[0])
        self.assertContains(response, tag[1])

    def test_release_channel(self):
        tag = (u'longcode', u'default10002')
        channel_key = u'%s:%s' % tag
        self.user_api.acquire_specific_tag(tag)
        self.assertEqual(set([tag]), self.user_api.list_endpoints())
        response = self.client.post(self.get_view_url('release', channel_key))
        self.assertRedirects(response, reverse('conversations:index'))
        self.assertEqual(set([]), self.user_api.list_endpoints())
