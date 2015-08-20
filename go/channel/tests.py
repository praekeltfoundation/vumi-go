from uuid import uuid4
import urllib

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse

    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.channel.views import get_channel_view_definition


class TestChannelViews(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.vumi_helper.setup_tagpool(
            u'longcode', [u'default1000%s' % i for i in [1, 2, 3, 4]])
        self.user_helper.add_tagpool_permission(u'longcode')
        self.client = self.vumi_helper.get_client()

    def assert_active_channel_tags(self, expected):
        self.assertEqual(
            set(':'.join(tag) for tag in expected),
            set(ch.key for ch in self.user_helper.user_api.active_channels()))

    def add_tagpool_permission(self, tagpool, max_keys=None):
        permission = self.api.account_store.tag_permissions(
            uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        permission.save()
        account = self.user_helper.user_api.get_user_account()
        account.tagpools.add(permission)
        account.save()

    def get_view_url(self, view, channel_key):
        view_def = get_channel_view_definition(None)
        return view_def.get_view_url(view, channel_key=channel_key)

    def test_index(self):
        tag = (u'longcode', u'default10001')
        channel_key = u'%s:%s' % tag
        response = self.client.get(reverse('channels:index'))
        self.assertNotContains(response, urllib.quote(channel_key))

        self.user_helper.user_api.acquire_specific_tag(tag)
        response = self.client.get(reverse('channels:index'))
        self.assertContains(response, urllib.quote(channel_key))

    def test_get_new_channel(self):
        self.assert_active_channel_tags([])
        response = self.client.get(reverse('channels:new_channel'))
        self.assertContains(response, 'International')
        self.assertContains(response, 'longcode:')

    def test_get_new_channel_empty_or_exhausted_tagpool(self):
        self.vumi_helper.setup_tagpool(u'empty', [])
        self.vumi_helper.setup_tagpool(u'exhausted', [u'tag1'])
        self.user_helper.add_tagpool_permission(u'empty')
        self.user_helper.add_tagpool_permission(u'exhausted')
        tag = self.user_helper.user_api.acquire_tag(u'exhausted')
        self.assert_active_channel_tags([tag])
        response = self.client.get(reverse('channels:new_channel'))
        self.assertContains(response, 'International')
        self.assertContains(response, 'longcode:')
        self.assertNotContains(response, 'empty:')
        self.assertNotContains(response, 'exhausted:')

    def test_post_new_channel(self):
        self.assert_active_channel_tags([])
        response = self.client.post(reverse('channels:new_channel'), {
            'country': 'International', 'channel': 'longcode:'})
        tag = (u'longcode', u'default10001')
        channel_key = u'%s:%s' % tag
        self.assertRedirects(response, self.get_view_url('show', channel_key))
        self.assert_active_channel_tags([tag])

    def test_post_new_channel_no_country(self):
        self.assert_active_channel_tags([])
        response = self.client.post(reverse('channels:new_channel'), {
            'channel': 'longcode:'})
        self.assertContains(response, '<li>country<ul class="errorlist">'
                            '<li>This field is required.</li></ul></li>')
        self.assert_active_channel_tags([])

    def test_post_new_channel_no_channel(self):
        self.assert_active_channel_tags([])
        response = self.client.post(reverse('channels:new_channel'), {
            'country': 'International'})
        self.assertContains(response, '<li>channel<ul class="errorlist">'
                            '<li>This field is required.</li></ul></li>')
        self.assert_active_channel_tags([])

    def test_show_channel_missing(self):
        response = self.client.get(self.get_view_url('show', u'foo:bar'))
        self.assertEqual(response.status_code, 404)

    def test_show_channel(self):
        tag = (u'longcode', u'default10002')
        channel_key = u'%s:%s' % tag
        self.user_helper.user_api.acquire_specific_tag(tag)
        response = self.client.get(self.get_view_url('show', channel_key))
        self.assertContains(response, tag[0])
        self.assertContains(response, tag[1])

    def test_release_channel(self):
        tag = (u'longcode', u'default10002')
        channel_key = u'%s:%s' % tag
        self.user_helper.user_api.acquire_specific_tag(tag)
        self.assert_active_channel_tags([tag])
        response = self.client.post(self.get_view_url('release', channel_key))
        self.assertRedirects(response, reverse('conversations:index'))
        self.assert_active_channel_tags([])
