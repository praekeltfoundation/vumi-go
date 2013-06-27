from uuid import uuid4

from django.test.client import Client
from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase, declare_longcode_tags
from go.base import utils as base_utils


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

    def test_get_new_channel(self):
        self.assertEqual(set([]), self.user_api.list_endpoints())
        response = self.client.get(reverse('channels:new_channel'))
        self.assertContains(response, 'International')
        self.assertContains(response, 'longcode:')

    def test_post_new_channel(self):
        self.assertEqual(set([]), self.user_api.list_endpoints())
        response = self.client.post(reverse('channels:new_channel'), {
            'country': 'International', 'channel': 'longcode:'})
        self.assertRedirects(response, reverse('conversations:index'))
        self.assertEqual(set([(u'longcode', u'default10001')]),
                         self.user_api.list_endpoints())
