import json
import logging
import csv
from datetime import date
from StringIO import StringIO
from zipfile import ZipFile

from django import forms
from django.core import mail
from django.core.urlresolvers import reverse
from django.utils.unittest import skip

from vumi.message import TransportUserMessage

import go.base.utils
import go.conversation.settings
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.conversation.templatetags import conversation_tags
from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)
from go.conversation.tasks import export_conversation_messages_unsorted
from go.vumitools.api import VumiApiCommand
from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)
from go.vumitools.conversation.utils import ConversationWrapper
from go.vumitools.tests.helpers import GoMessageHelper
from go.dashboard.dashboard import DashboardLayout, DashboardParseError
from go.dashboard import client as dashboard_client
from go.dashboard.tests.utils import FakeDiamondashApiClient


class EnabledAction(ConversationAction):
    action_name = 'enabled'
    action_display_name = 'Enabled Operation'

    def check_disabled(self):
        return None

    def perform_action(self, action_data):
        pass


class DisabledAction(ConversationAction):
    action_name = 'disabled'
    action_display_name = 'Disabled Operation'

    def check_disabled(self):
        return "This action is disabled."

    def perform_action(self, action_data):
        raise Exception("This action should never be performed.")


class DummyConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'dummy'
    conversation_display_name = 'Dummy Conversation'


class ActionConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'with_actions'
    conversation_display_name = 'Conversation With Actions'
    actions = (EnabledAction, DisabledAction)


class EndpointConversationDefinition(ConversationDefinitionBase):
    conversation_type = u'extra_endpoints'
    conversation_display_name = u'Extra Endpoints'
    extra_static_endpoints = (u'extra',)


class SimpleEditForm(forms.Form):
    simple_field = forms.CharField()


class SimpleEditView(EditConversationView):
    edit_forms = (
        (None, SimpleEditForm),
    )


class SimpleEditConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'simple_edit'
    conversation_display_name = 'Simple Editable Conversation'


class SimpleEditViewDefinition(ConversationViewDefinitionBase):
    edit_view = SimpleEditView


class ComplexEditView(EditConversationView):
    edit_forms = (
        ('foo', SimpleEditForm),
        ('bar', SimpleEditForm),
    )


class ComplexEditConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'complex_edit'
    conversation_display_name = 'Complex Editable Conversation'


class ComplexEditViewDefinition(ConversationViewDefinitionBase):
    edit_view = ComplexEditView


class DefaultConfigConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'default_config'
    conversation_display_name = 'Default Config Conversation'

    def get_default_config(self, name, description):
        return {
            'name': name,
            'description': description,
        }


DUMMY_CONVERSATION_DEFS = {
    'dummy': (
        DummyConversationDefinition, ConversationViewDefinitionBase),
    'with_actions': (
        ActionConversationDefinition, ConversationViewDefinitionBase),
    'extra_endpoints': (
        EndpointConversationDefinition, ConversationViewDefinitionBase),
    'simple_edit': (
        SimpleEditConversationDefinition, SimpleEditViewDefinition),
    'complex_edit': (
        ComplexEditConversationDefinition, ComplexEditViewDefinition),
    'default_config': (
        DefaultConfigConversationDefinition, ConversationViewDefinitionBase),
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


class BaseConversationViewTestCase(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper(), setup_vumi_api=False)
        self.monkey_patch(
            go.base.utils, 'get_conversation_pkg', self._get_conversation_pkg)
        self.vumi_helper.patch_config(
            VUMI_INSTALLED_APPS=DUMMY_CONVERSATION_SETTINGS)
        self.vumi_helper.setup_vumi_api()
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def _get_conversation_pkg(self, conversation_type, from_list=()):
        """Test stub for `go.base.utils.get_conversation_pkg()`
        """
        return FakeConversationPackage(conversation_type)

    def get_view_url(self, conv, view):
        view_def = go.base.utils.get_conversation_view_definition(
            conv.conversation_type)
        return view_def.get_view_url(view, conversation_key=conv.key)

    def get_new_view_url(self):
        return reverse('conversations:new_conversation')

    def get_action_view_url(self, conv, action_name):
        return reverse('conversations:conversation_action', kwargs={
            'conversation_key': conv.key, 'action_name': action_name})

    def get_api_commands_sent(self):
        return go.base.utils.connection.get_commands()


class TestConversationsDashboardView(BaseConversationViewTestCase):

    def test_index(self):
        """Display all conversations"""
        response = self.client.get(reverse('conversations:index'))
        self.assertNotContains(response, u'myconv')

        myconv = self.user_helper.create_conversation(u'dummy', name=u'myconv')
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, u'myconv')
        self.assertContains(response, u'Dummy Conversation')

        self.assertContains(response, self.get_view_url(myconv, 'show'))
        self.assertContains(response, self.get_view_url(
            myconv, 'message_list'))
        self.assertContains(response, self.get_view_url(myconv, 'reports'))

    def test_index_search(self):
        """Filter conversations based on query string"""
        conv = self.user_helper.create_conversation(u'dummy')

        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, conv.name)

        response = self.client.get(reverse('conversations:index'), {
            'query': 'something that does not exist in the fixtures'})
        self.assertNotContains(response, conv.name)

    def test_index_search_on_type(self):
        conv = self.user_helper.create_conversation(u'dummy')
        self.user_helper.add_app_permission(u'gotest.dummy')
        self.user_helper.add_app_permission(u'gotest.with_actions')

        def search(conversation_type):
            return self.client.get(reverse('conversations:index'), {
                'query': conv.name,
                'conversation_type': conversation_type,
            })

        self.assertContains(search('dummy'), conv.key)
        self.assertNotContains(search('with_actions'), conv.key)

    def test_index_search_on_status(self):
        conv = self.user_helper.create_conversation(u'dummy')

        def search(conversation_status):
            return self.client.get(reverse('conversations:index'), {
                'query': conv.name,
                'conversation_status': conversation_status,
            })

        # it should be draft
        self.assertContains(search('draft'), conv.key)
        self.assertNotContains(search('running'), conv.key)
        self.assertNotContains(search('finished'), conv.key)

        # Set the status to `running'
        conv = self.user_helper.get_conversation(conv.key)
        conv.set_status_started()
        conv.save()
        self.assertNotContains(search('draft'), conv.key)
        self.assertContains(search('running'), conv.key)
        self.assertNotContains(search('finished'), conv.key)

        # Set the status to `stopped' again
        conv = self.user_helper.get_conversation(conv.key)
        conv.set_status_stopped()
        conv.save()
        self.assertContains(search('draft'), conv.key)
        self.assertNotContains(search('running'), conv.key)
        self.assertNotContains(search('finished'), conv.key)

        # Archive it
        conv.archive_conversation()

        self.assertNotContains(search('draft'), conv.key)
        self.assertNotContains(search('running'), conv.key)
        self.assertContains(search('finished'), conv.key)

    def test_pagination(self):
        for i in range(13):
            conv = self.user_helper.create_conversation(u'dummy')
        response = self.client.get(reverse('conversations:index'))
        # CONVERSATIONS_PER_PAGE = 12
        self.assertContains(response, conv.name, count=12)
        response = self.client.get(reverse('conversations:index'), {'p': 2})
        self.assertContains(response, conv.name, count=1)

    def test_pagination_with_query_and_type(self):
        self.user_helper.add_app_permission(u'gotest.dummy')
        self.user_helper.add_app_permission(u'gotest.with_actions')
        for i in range(13):
            conv = self.user_helper.create_conversation(u'dummy')
        response = self.client.get(reverse('conversations:index'), {
            'query': conv.name,
            'p': 2,
            'conversation_type': 'dummy',
            'conversation_status': 'draft',
        })

        self.assertNotContains(response, '?p=2')


class TestNewConversationView(BaseConversationViewTestCase):
    def test_get_new_conversation(self):
        self.user_helper.add_app_permission(u'gotest.dummy')
        response = self.client.get(reverse('conversations:new_conversation'))
        self.assertContains(response, 'Conversation name')
        self.assertContains(response, 'kind of conversation')
        self.assertContains(response, 'dummy')
        self.assertNotContains(response, 'with_actions')

    def test_post_new_conversation(self):
        self.user_helper.add_app_permission(u'gotest.dummy')
        conv_data = {
            'name': 'new conv',
            'conversation_type': 'dummy',
        }
        response = self.client.post(
            reverse('conversations:new_conversation'), conv_data)
        [conv] = self.user_helper.user_api.active_conversations()
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        self.assertEqual(conv.name, 'new conv')
        self.assertEqual(conv.conversation_type, 'dummy')

    def test_post_new_conversation_extra_endpoints(self):
        self.user_helper.add_app_permission(u'gotest.extra_endpoints')
        conv_data = {
            'name': 'new conv',
            'conversation_type': 'extra_endpoints',
        }
        response = self.client.post(reverse('conversations:new_conversation'),
                                    conv_data)
        [conv] = self.user_helper.user_api.active_conversations()
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        self.assertEqual(conv.name, 'new conv')
        self.assertEqual(conv.conversation_type, 'extra_endpoints')
        self.assertEqual(list(conv.extra_endpoints), [u'extra'])

    def test_post_new_conversation_default_config(self):
        self.user_helper.add_app_permission(u'gotest.default_config')
        conv_data = {
            'name': 'new conv',
            'description': 'a new conversation',
            'conversation_type': 'default_config',
        }
        self.client.post(reverse('conversations:new_conversation'), conv_data)
        [conv] = self.user_helper.user_api.active_conversations()
        self.assertEqual(conv.config, {
            'name': 'new conv',
            'description': 'a new conversation'
        })

    def test_post_new_conversation_starting(self):
        self.user_helper.add_app_permission(u'gotest.dummy')

        conv_data = {
            'name': 'new conv',
            'conversation_type': 'dummy',
        }

        response = self.client.post(
            reverse('conversations:new_conversation'),
            conv_data)

        [conv] = self.user_helper.user_api.active_conversations()
        self.assertTrue(conv.starting())


class TestConversationViews(BaseConversationViewTestCase):

    def setUp(self):
        super(TestConversationViews, self).setUp()
        self.msg_helper = self.add_helper(
            GoMessageHelper(vumi_helper=self.vumi_helper))

    def enable_event_statuses(self):
        self.monkey_patch(
            go.conversation.settings, 'ENABLE_EVENT_STATUSES_IN_MESSAGE_LIST',
            True)

    def test_show_no_content_block(self):
        conv = self.user_helper.create_conversation(u'dummy')
        show_url = self.get_view_url(conv, 'show')
        response = self.client.get(show_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Content')
        self.assertNotContains(response, show_url + 'edit/')

    def test_show_editable(self):
        conv = self.user_helper.create_conversation(u'simple_edit')
        response = self.client.get(self.get_view_url(conv, 'show'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Content')
        self.assertContains(response, self.get_view_url(conv, 'edit'))

    def test_edit_simple(self):
        conv = self.user_helper.create_conversation(u'simple_edit')
        self.assertEqual(conv.config, {})

        response = self.client.get(self.get_view_url(conv, 'edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'simple_field')
        self.assertNotContains(response, 'field value')

        response = self.client.post(self.get_view_url(conv, 'edit'), {
            'simple_field': ['field value'],
        })
        self.assertRedirects(response, self.get_view_url(conv, 'show'))
        conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(conv.config, {'simple_field': 'field value'})

        response = self.client.get(self.get_view_url(conv, 'edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'simple_field')
        self.assertContains(response, 'field value')

    def test_edit_complex(self):
        conv = self.user_helper.create_conversation(u'complex_edit')
        self.assertEqual(conv.config, {})

        response = self.client.get(self.get_view_url(conv, 'edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'foo-simple_field')
        self.assertContains(response, 'bar-simple_field')
        self.assertNotContains(response, 'field value 1')
        self.assertNotContains(response, 'field value 2')

        response = self.client.post(self.get_view_url(conv, 'edit'), {
            'foo-simple_field': ['field value 1'],
            'bar-simple_field': ['field value 2'],
        })
        self.assertRedirects(response, self.get_view_url(conv, 'show'))
        conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(conv.config, {
            'foo': {'simple_field': 'field value 1'},
            'bar': {'simple_field': 'field value 2'},
        })

        response = self.client.get(self.get_view_url(conv, 'edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'foo-simple_field')
        self.assertContains(response, 'bar-simple_field')
        self.assertContains(response, 'field value 1')
        self.assertContains(response, 'field value 2')

    def test_edit_conversation_details_get(self):
        conv = self.user_helper.create_conversation(
            u'dummy', name=u'test-name', description=u'test-desc')

        response = self.client.get(
            reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': 'edit_detail/',
            }))

        print response
        self.assertContains(response, "Edit test-name details")
        self.assertContains(response, "Save")
        self.assertContains(response, "Conversation name")
        self.assertContains(response, 'value="test-name"')
        self.assertContains(response, "Conversation description")
        self.assertContains(response, 'value="test-desc"')

    def test_edit_conversation_details_submit(self):
        conv = self.user_helper.create_conversation(
            u'dummy', name=u'test', description=u'test')

        response = self.client.post(
            reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': 'edit_detail/',
            }), {
                'name': 'foo',
                'description': 'bar',
            })
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        reloaded_conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(reloaded_conv.name, 'foo')
        self.assertEqual(reloaded_conv.description, 'bar')

    def test_edit_conversation_details_submit_invalid_form(self):
        conv = self.user_helper.create_conversation(
            u'dummy', name=u'test-name', description=u'test-desc')

        response = self.client.post(
            reverse('conversations:conversation', kwargs={
                'conversation_key': conv.key, 'path_suffix': 'edit_detail/',
            }), {
                'name': '',
                'description': 'bar',
            })

        self.assertContains(response, "This field is required.")

        reloaded_conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(reloaded_conv.name, 'test-name')
        self.assertEqual(reloaded_conv.description, 'test-desc')

    def test_edit_fallback(self):
        conv = self.user_helper.create_conversation(u'dummy')
        response = self.client.get(self.get_view_url(conv, 'edit'))
        self.assertRedirects(response, self.get_view_url(conv, 'show'))

    def test_conversation_contact_group_listing(self):
        conv = self.user_helper.create_conversation(
            u'dummy', name=u'test', description=u'test')
        contact_store = self.user_helper.user_api.contact_store
        group1 = contact_store.new_group(u'Contact Group 1')
        group2 = contact_store.new_group(u'Contact Group 2')

        conv.add_group(group1)
        conv.save()

        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})

        resp = self.client.get(show_url)
        self.assertContains(resp, group1.name)
        self.assertNotContains(resp, group2.name)

    def test_conversation_render_contact_group_edit(self):
        conv = self.user_helper.create_conversation(
            u'dummy', name=u'test', description=u'test')
        contact_store = self.user_helper.user_api.contact_store
        group1 = contact_store.new_group(u'Contact Group 1')
        group2 = contact_store.new_group(u'Contact Group 2')

        conv.add_group(group1)
        conv.save()

        groups_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key,
            'path_suffix': 'edit_groups/'
        })

        response = self.client.get(groups_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.context['model_data']), {
            'key': conv.key,
            'urls': {
                'show': reverse(
                    'conversations:conversation', kwargs={
                        'conversation_key': conv.key,
                        'path_suffix': ''
                    })
            },
            'groups': [{
                'key': group2.key,
                'name': u'Contact Group 2',
                'inConversation': False,
                'urls': {
                    'show': reverse(
                        'contacts:group',
                        kwargs={'group_key': group2.key}),
                },
            }, {
                'key': group1.key,
                'name': u'Contact Group 1',
                'inConversation': True,
                'urls': {
                    'show': reverse(
                        'contacts:group',
                        kwargs={'group_key': group1.key}),
                },
            }]
        })

    def test_conversation_contact_group_assignment(self):
        conv = self.user_helper.create_conversation(
            u'dummy', name=u'test', description=u'test')
        contact_store = self.user_helper.user_api.contact_store
        contact_store.new_group(u'Contact Group 1')
        group2 = contact_store.new_group(u'Contact Group 2')
        group3 = contact_store.new_group(u'Contact Group 3')

        groups_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': 'edit_groups/'})

        resp = self.client.put(
            groups_url,
            content_type='application/json',
            data=json.dumps({
                'key': conv.key,
                'groups': [
                    {'key': group2.key},
                    {'key': group3.key}]
            }))

        self.assertEqual(resp.status_code, 200)

    def test_start(self):
        conv = self.user_helper.create_conversation(u'dummy')

        response = self.client.post(
            self.get_view_url(conv, 'start'), follow=True)
        self.assertRedirects(response, self.get_view_url(conv, 'show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Dummy Conversation started")

        conv = self.user_helper.get_conversation(conv.key)
        self.assertTrue(conv.starting())
        [start_cmd] = self.get_api_commands_sent()
        self.assertEqual(start_cmd, VumiApiCommand.command(
            '%s_application' % (conv.conversation_type,), 'start',
            command_id=start_cmd["command_id"],
            user_account_key=conv.user_account.key, conversation_key=conv.key))

    def test_stop(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)

        response = self.client.post(
            self.get_view_url(conv, 'stop'), follow=True)
        self.assertRedirects(response, self.get_view_url(conv, 'show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Dummy Conversation stopped")

        conv = self.user_helper.get_conversation(conv.key)
        self.assertTrue(conv.stopping())

    def test_aggregates(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        # Inbound only
        self.msg_helper.add_inbound_to_conv(
            conv, 5, start_date=date(2012, 1, 1), time_multiplier=12)
        # Inbound and outbound
        msgs = self.msg_helper.add_inbound_to_conv(
            conv, 5, start_date=date(2013, 1, 1), time_multiplier=12)
        self.msg_helper.add_replies_to_conv(conv, msgs)
        response = self.client.get(
            self.get_view_url(conv, 'aggregates'), {'direction': 'inbound'})
        self.assertEqual(response.content, '\r\n'.join([
            '2011-12-30,1',
            '2011-12-31,2',
            '2012-01-01,2',
            '2012-12-30,1',
            '2012-12-31,2',
            '2013-01-01,2',
            '',  # csv ends with a blank line
            ]))

        response = self.client.get(
            self.get_view_url(conv, 'aggregates'), {'direction': 'outbound'})
        self.assertEqual(response.content, '\r\n'.join([
            '2012-12-30,1',
            '2012-12-31,2',
            '2013-01-01,2',
            '',  # csv ends with a blank line
            ]))

    def test_export_csv_messages(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        msgs = self.msg_helper.add_inbound_to_conv(
            conv, 5, start_date=date(2012, 1, 1), time_multiplier=12)
        self.msg_helper.add_replies_to_conv(conv, msgs)
        response = self.client.post(self.get_view_url(conv, 'export_messages'))
        self.assertRedirects(response, self.get_view_url(conv, 'message_list'))
        [email] = mail.outbox
        self.assertEqual(
            email.recipients(), [self.user_helper.get_django_user().email])
        self.assertTrue(conv.name in email.subject)
        self.assertTrue(conv.name in email.body)
        [(file_name, zipcontent, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')
        zipfile = ZipFile(StringIO(zipcontent), 'r')
        content = zipfile.open('messages-export.csv', 'r').read()
        # 1 header, 5 sent, 5 received, 1 trailing newline == 12
        self.assertEqual(12, len(content.split('\n')))
        self.assertEqual(mime_type, 'application/zip')

    def test_download_json_messages_inbound(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get(self.get_view_url(conv, 'export_messages'))
        self.assertEqual(
            response['X-Accel-Redirect'],
            '/message_store_exporter/%s/inbound.json' % (conv.batch.key,))
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename=%s-inbound.json' % (conv.key,))
        self.assertEqual(response['X-Accel-Buffering'], 'no')

    def test_download_csv_messages_inbound(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get("%s?format=csv" % (
            self.get_view_url(conv, 'export_messages')))
        self.assertEqual(
            response['X-Accel-Redirect'],
            '/message_store_exporter/%s/inbound.csv' % (conv.batch.key,))
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename=%s-inbound.csv' % (conv.key,))
        self.assertEqual(response['X-Accel-Buffering'], 'no')

    def test_download_json_messages_outbound(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get('%s?direction=outbound' % (
            self.get_view_url(conv, 'export_messages'),))
        self.assertEqual(
            response['X-Accel-Redirect'],
            '/message_store_exporter/%s/outbound.json' % (conv.batch.key,))
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename=%s-outbound.json' % (conv.key,))
        self.assertEqual(response['X-Accel-Buffering'], 'no')

    def test_download_csv_messages_outbound(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get('%s?direction=outbound&format=csv' % (
            self.get_view_url(conv, 'export_messages'),))
        self.assertEqual(
            response['X-Accel-Redirect'],
            '/message_store_exporter/%s/outbound.csv' % (conv.batch.key,))
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename=%s-outbound.csv' % (conv.key,))
        self.assertEqual(response['X-Accel-Buffering'], 'no')

    def test_download_messages_unknown_direction_404(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get('%s?direction=unknown&format=json' % (
            self.get_view_url(conv, 'export_messages'),))
        self.assertEqual(response.status_code, 404)

    def test_download_messages_unknown_format_404(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get('%s?direction=outbound&format=unknown' % (
            self.get_view_url(conv, 'export_messages'),))
        self.assertEqual(response.status_code, 404)

    def test_message_list_pagination(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        # Create 21 inbound messages, since we have 20 messages per page it
        # should give us 2 pages
        self.msg_helper.add_inbound_to_conv(conv, 21)
        response = self.client.get(self.get_view_url(conv, 'message_list'))

        # Check pagination
        # Ordinarily we'd have 60 references to a contact, which by default
        # display the from_addr if a contact cannot be found. (Each block has 3
        # references, one in the table listing, 2 in the reply-to modal div.)
        # We have no channels connected to this conversation, however, so we
        # only have 20 in this test.
        self.assertContains(response, 'from-', 20)
        # We should have 2 links to page two, one for the actual page link
        # and one for the 'Next' page link
        self.assertContains(response, '&amp;p=2', 2)
        # There should only be 1 link to the current page
        self.assertContains(response, '&amp;p=1', 1)
        # There should not be a link to the previous page since we are not
        # the first page.
        self.assertContains(response, '&amp;p=0', 0)

    def test_message_list_statistics(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        msgs = self.msg_helper.add_inbound_to_conv(conv, 10)
        replies = self.msg_helper.add_replies_to_conv(conv, msgs)
        for msg in replies[:4]:
            self.msg_helper.make_stored_ack(conv, msg)
        for msg in replies[4:9]:
            self.msg_helper.make_stored_nack(conv, msg)
        for msg in replies[:2]:
            self.msg_helper.make_stored_delivery_report(
                conv, msg, delivery_status='delivered')
        for msg in replies[2:5]:
            self.msg_helper.make_stored_delivery_report(
                conv, msg, delivery_status='pending')
        for msg in replies[5:9]:
            self.msg_helper.make_stored_delivery_report(
                conv, msg, delivery_status='failed')

        response = self.client.get(self.get_view_url(conv, 'message_list'))

        self.assertContains(
            response,
            '<tr><th>Total&nbsp;sent</th><td colspan="2">10</td></tr>',
            html=True)

        self.assertContains(
            response, '<tr><th>Accepted</th><td>4</td><td>40%</td></tr>',
            html=True)
        self.assertContains(
            response, '<tr><th>Rejected</th><td>5</td><td>50%</td></tr>',
            html=True)

        self.assertContains(
            response, '<tr><th>Delivered</th><td>2</td><td>20%</td></tr>',
            html=True)
        self.assertContains(
            response, '<tr><th>Pending</th><td>3</td><td>30%</td></tr>',
            html=True)
        self.assertContains(
            response, '<tr><th>Failed</th><td>4</td><td>40%</td></tr>',
            html=True)

    def test_message_list_inbound_uniques_display(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        self.msg_helper.add_inbound_to_conv(conv, 10)
        response = self.client.get(self.get_view_url(conv, 'message_list'))
        self.assertContains(response, 'Messages from 10 unique people')

    def test_message_list_inbound_download_links_display(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get(self.get_view_url(conv, 'message_list'))
        inbound_json_url = ('%s?direction=inbound&format=json' %
                            self.get_view_url(conv, 'export_messages'))
        self.assertContains(response, 'href="%s"' % inbound_json_url)
        self.assertContains(response, "Download received messages as JSON")
        inbound_csv_url = ('%s?direction=inbound&format=csv' %
                           self.get_view_url(conv, 'export_messages'))
        self.assertContains(response, 'href="%s"' % inbound_csv_url)
        self.assertContains(response, "Download received messages as CSV")

    def test_message_list_outbound_uniques_display(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        msgs = self.msg_helper.add_inbound_to_conv(conv, 10)
        self.msg_helper.add_replies_to_conv(conv, msgs)
        response = self.client.get(
            self.get_view_url(conv, 'message_list'), {
                'direction': 'outbound'
            })
        self.assertContains(response, 'Messages to 10 unique people')

    def test_message_list_outbound_download_links_display(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        response = self.client.get(
            self.get_view_url(conv, 'message_list'), {
                'direction': 'outbound'
            })
        outbound_json_url = ('%s?direction=outbound&format=json' %
                             self.get_view_url(conv, 'export_messages'))
        self.assertContains(response, 'href="%s"' % outbound_json_url)
        self.assertContains(response, "Download sent messages as JSON")
        outbound_csv_url = ('%s?direction=outbound&format=csv' %
                            self.get_view_url(conv, 'export_messages'))
        self.assertContains(response, 'href="%s"' % outbound_csv_url)
        self.assertContains(response, "Download sent messages as CSV")

    def test_message_list_no_sensitive_msgs(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)

        def make_stored_msgs(go_metadata={}):
            self.msg_helper.make_stored_inbound(
                conv, "hi", from_addr='from-me',
                helper_metadata={'go': go_metadata})
            self.msg_helper.make_stored_outbound(
                conv, "hi", to_addr='from-me',
                helper_metadata={'go': go_metadata})

        def assert_messages(count):
            r_in = self.client.get(
                self.get_view_url(conv, 'message_list'),
                {'direction': 'inbound'})
            self.assertContains(r_in, 'from-me', count)
            r_out = self.client.get(
                self.get_view_url(conv, 'message_list'),
                {'direction': 'outbound'})
            self.assertContains(r_out, 'from-me', count)

        assert_messages(0)
        make_stored_msgs()
        assert_messages(1)
        make_stored_msgs({'sensitive': True})
        assert_messages(1)
        make_stored_msgs({'sensitive': False})
        assert_messages(2)

    def test_message_list_outbound_statuses_disabled(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        self.msg_helper.make_stored_outbound(conv, "hi")

        r_out = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'outbound'})
        self.assertContains(r_out, "<td>-", html=True)
        self.assertNotContains(r_out, "<td>Sending", html=True)
        self.assertNotContains(r_out, "<td>Accepted", html=True)
        self.assertNotContains(r_out, "<td>Rejected", html=True)

    def test_message_list_outbound_status_pending(self):
        self.enable_event_statuses()
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        self.msg_helper.make_stored_outbound(conv, "hi")

        r_out = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'outbound'})
        self.assertContains(r_out, "<td>Sending", html=True)
        self.assertNotContains(r_out, "<td>Accepted", html=True)
        self.assertNotContains(r_out, "<td>Rejected", html=True)

    def test_message_list_outbound_status_failed(self):
        self.enable_event_statuses()
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        msg = self.msg_helper.make_stored_outbound(conv, "hi")
        self.msg_helper.make_stored_nack(conv, msg, nack_reason="no spoons")

        r_out = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'outbound'})
        self.assertContains(r_out, "<td>Rejected: no spoons", html=True)
        self.assertNotContains(r_out, "<td>Sending", html=True)
        self.assertNotContains(r_out, "<td>Accepted", html=True)

    def test_message_list_outbound_status_sent(self):
        self.enable_event_statuses()
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        msg = self.msg_helper.make_stored_outbound(conv, "hi")
        self.msg_helper.make_stored_ack(conv, msg)

        r_out = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'outbound'})
        self.assertContains(r_out, "<td>Accepted", html=True)
        self.assertNotContains(r_out, "<td>Sending", html=True)
        self.assertNotContains(r_out, "<td>Rejected", html=True)

    def test_message_list_with_bad_transport_type_inbound(self):
        # inbound messages could have an unsupported transport_type
        # if the transport sent something we don't yet support
        conv = self.user_helper.create_conversation(u'dummy', started=True)

        self.msg_helper.make_stored_inbound(
            conv, "hi", transport_type="bad horse", from_addr='from-me')

        r_in = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'inbound'})

        self.assertContains(r_in, 'from-me', 1)
        self.assertContains(r_in, 'bad horse (unsupported)', 1)

    def test_message_list_with_bad_transport_type_outbound(self):
        # unsent message don't have their transport type set to something
        # that a contact can be created for
        conv = self.user_helper.create_conversation(u'dummy', started=True)

        self.msg_helper.make_stored_outbound(
            conv, "hi", transport_type="bad horse", to_addr='from-me')

        r_out = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'outbound'})

        self.assertContains(r_out, 'from-me', 1)
        self.assertContains(r_out, 'bad horse (unsupported)', 1)

    def test_reply_on_inbound_messages_only(self):
        # Fake the routing setup.
        self.monkey_patch(
            ConversationWrapper, 'has_channel_supporting_generic_sends',
            lambda s: True)
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        [msg_in] = self.msg_helper.add_inbound_to_conv(conv, 1)
        [msg_out] = self.msg_helper.add_replies_to_conv(conv, [msg_in])

        response = self.client.get(
            self.get_view_url(conv, 'message_list'), {'direction': 'inbound'})
        self.assertContains(response, 'Reply')
        self.assertContains(response, 'href="#reply-%s"' % (
            msg_in['message_id'],))

        response = self.client.get(
            self.get_view_url(conv, 'message_list'), {'direction': 'outbound'})
        self.assertNotContains(response, 'Reply')

    def test_no_reply_with_no_generic_send_channels(self):
        # We have no routing hooked up and hence no channels supporting generic
        # sends.
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        self.msg_helper.add_inbound_to_conv(conv, 1)

        response = self.client.get(
            self.get_view_url(conv, 'message_list'), {'direction': 'inbound'})
        self.assertNotContains(response, 'Reply')

    def test_send_one_off_reply(self):
        conv = self.user_helper.create_conversation(u'dummy', started=True)
        self.msg_helper.add_inbound_to_conv(conv, 1)
        [msg] = conv.received_messages_in_cache()
        response = self.client.post(self.get_view_url(conv, 'message_list'), {
            'in_reply_to': msg['message_id'],
            'content': 'foo',
            'to_addr': 'should be ignored',
            '_send_one_off_reply': True,
        })
        self.assertRedirects(response, self.get_view_url(conv, 'message_list'))

        [reply_to_cmd] = self.get_api_commands_sent()
        self.assertEqual(reply_to_cmd['worker_name'], 'dummy_application')
        self.assertEqual(reply_to_cmd['command'], 'send_message')
        self.assertEqual(
            reply_to_cmd['args'], [conv.user_account.key, conv.key])
        self.assertEqual(reply_to_cmd['kwargs']['command_data'], {
            'batch_id': conv.batch.key,
            'conversation_key': conv.key,
            'content': 'foo',
            'to_addr': msg['from_addr'],
            'msg_options': {'in_reply_to': msg['message_id']},
        })


class TestConversationTemplateTags(BaseConversationViewTestCase):
    def _assert_cs_url(self, suffix, conv, view_name=None):
        expected = '/conversations/%s/%s' % (conv.key, suffix)
        if view_name is None:
            result = conversation_tags.conversation_screen(conv)
        else:
            result = conversation_tags.conversation_screen(conv, view_name)
        self.assertEqual(expected, result)

    def test_conversation_screen_tag(self):
        conv = self.user_helper.create_conversation(u'dummy')
        self._assert_cs_url('', conv)
        self._assert_cs_url('', conv, 'show')
        self._assert_cs_url('edit_detail/', conv, 'edit_detail')
        self._assert_cs_url('start/', conv, 'start')
        # The dummy conversation isn't editable.
        self.assertRaises(Exception, self._assert_cs_url, '', conv, 'edit')

    def _assert_ca_url(self, suffix, conv, action_name):
        expected = '/conversations/%s/action/%s' % (conv.key, suffix)
        result = conversation_tags.conversation_action(conv, action_name)
        self.assertEqual(expected, result)

    def test_conversation_action_tag(self):
        conv = self.user_helper.create_conversation(u'with_actions')
        self._assert_ca_url('enabled', conv, 'enabled')
        self._assert_ca_url('disabled', conv, 'disabled')
        # The conversation_action tag currently just builds a URL without
        # regard to the existence of the action.
        self._assert_ca_url('foo', conv, 'foo')

    @skip("TODO")
    def test_get_contact_for_message(self):
        raise NotImplementedError("TODO")

    @skip("TODO")
    def test_get_reply_form_for_message(self):
        raise NotImplementedError("TODO")


class TestConversationReportsView(BaseConversationViewTestCase):
    def setUp(self):
        super(TestConversationReportsView, self).setUp()
        self.diamondash_api = FakeDiamondashApiClient()

        self.error_log = []
        logger = logging.getLogger('go.conversation.view_definition')

        def log_error(e, exc_info):
            exc_type, exc_value, exc_traceback = exc_info
            self.assertEqual(e, exc_value)
            self.error_log.append(unicode(e))

        self.monkey_patch(logger, 'error', log_error)

        self.monkey_patch(
            dashboard_client,
            'get_diamondash_api',
            lambda: self.diamondash_api)

    def test_get_dashboard(self):
        self.diamondash_api.set_response({'happy': 'dashboard'})

        conv = self.user_helper.create_conversation(u'dummy')
        response = self.client.get(self.get_view_url(conv, 'reports'))

        [dd_request] = self.diamondash_api.get_requests()
        raw_dashboard = dd_request['data']

        self.assertEqual(
            raw_dashboard['name'],
            "go.conversations.%s" % conv.key)

        self.assertTrue('widgets' in raw_dashboard)

        self.assertEqual(
            json.loads(response.context['dashboard_config']),
            {'happy': 'dashboard'})

    def test_get_dashboard_for_sync_error_handling(self):
        self.diamondash_api.set_error_response(400, ':(')

        conv = self.user_helper.create_conversation(u'dummy')
        response = self.client.get(self.get_view_url(conv, 'reports'))

        self.assertEqual(
            self.error_log,
            ['Dashboard sync failed: '
             '400: {"message": ":(", "success": false}'])

        self.assertEqual(response.context['dashboard_config'], None)

    def test_get_dashboard_for_parse_error_handling(self):
        conv = self.user_helper.create_conversation(u'dummy')

        def bad_add_entity(*a, **kw):
            raise DashboardParseError(':(')

        self.monkey_patch(DashboardLayout, 'add_entity', bad_add_entity)
        response = self.client.get(self.get_view_url(conv, 'reports'))

        self.assertEqual(self.error_log, [':('])
        self.assertEqual(response.context['dashboard_config'], None)


class TestConversationTasks(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.msg_helper = self.add_helper(
            GoMessageHelper(vumi_helper=self.vumi_helper))

    def create_conversation(self, name=u'dummy', reply_count=5,
                            time_multiplier=12,
                            start_date=date(2013, 1, 1)):
        conv = self.user_helper.create_conversation(name)
        if reply_count:
            inbound_msgs = self.msg_helper.add_inbound_to_conv(
                conv, reply_count, start_date=start_date,
                time_multiplier=time_multiplier)
            self.msg_helper.add_replies_to_conv(conv, inbound_msgs)
        return conv

    def get_attachment(self, email, file_name):
        for attachment in email.attachments:
            fn, attachment_content, mime_type = attachment
            if fn == file_name:
                return StringIO(attachment_content)

    def get_zipfile_attachment(
            self, email, attachment_file_name, zipfile_file_name):
        attachment = self.get_attachment(email, attachment_file_name)
        zipfile = ZipFile(attachment, 'r')
        return zipfile.open(zipfile_file_name, 'r')

    def test_export_conversation_messages_unsorted(self):
        conv = self.create_conversation()
        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        self.assertEqual(
            email.recipients(), [self.user_helper.get_django_user().email])
        self.assertTrue(conv.name in email.subject)
        self.assertTrue(conv.name in email.body)
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        message_ids = [row['message_id'] for row in reader]
        all_keys = set()
        index_page = conv.qms.list_batch_inbound_messages(conv.batch.key)
        while index_page is not None:
            all_keys.update(mt[0] for mt in index_page)
            index_page = index_page.next_page()
        index_page = conv.qms.list_batch_outbound_messages(conv.batch.key)
        while index_page is not None:
            all_keys.update(mt[0] for mt in index_page)
            index_page = index_page.next_page()
        self.assertEqual(set(message_ids), all_keys)

    def test_export_conversation_message_session_events(self):
        conv = self.create_conversation(reply_count=0)
        msg = self.msg_helper.make_stored_inbound(
            conv, "inbound", from_addr='from-1',
            session_event=TransportUserMessage.SESSION_NEW)

        reply = self.msg_helper.make_reply(
            msg, "reply", session_event=TransportUserMessage.SESSION_CLOSE)

        self.msg_helper.store_outbound(conv, reply)

        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        events = [row['session_event'] for row in reader]
        self.assertEqual(
            set(events),
            set([TransportUserMessage.SESSION_NEW,
                 TransportUserMessage.SESSION_CLOSE]))

    def test_export_conversation_message_transport_types(self):
        conv = self.create_conversation(reply_count=0)
        # SMS message
        self.msg_helper.make_stored_inbound(
            conv, "inbound", from_addr='from-1', transport_type='sms')
        # USSD message
        self.msg_helper.make_stored_inbound(
            conv, "inbound", from_addr='from-1', transport_type='ussd')

        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        events = [row['transport_type'] for row in reader]
        self.assertEqual(
            set(events),
            set(['sms', 'ussd']))

    def test_export_conversation_message_directions(self):
        conv = self.create_conversation()
        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        directions = [row['direction'] for row in reader]
        self.assertEqual(
            set(directions),
            set(['inbound', 'outbound']))

    def test_export_conversation_delivery_status(self):
        conv = self.create_conversation(reply_count=0)

        msg = self.msg_helper.make_stored_outbound(
            conv, "outbound", to_addr='from-1')
        self.msg_helper.make_stored_delivery_report(msg=msg, conv=conv)

        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        delivery_statuses = [row['delivery_status'] for row in reader]
        self.assertEqual(set(delivery_statuses), set(['delivered']))

    def test_export_conversation_ack(self):
        conv = self.create_conversation(reply_count=0)

        msg = self.msg_helper.make_stored_outbound(
            conv, "outbound", to_addr='from-1')
        self.msg_helper.make_stored_ack(msg=msg, conv=conv)

        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        [row] = list(reader)
        self.assertEqual(row['network_handover_status'], 'ack')

    def test_export_conversation_nack(self):
        conv = self.create_conversation(reply_count=0)

        msg = self.msg_helper.make_stored_outbound(
            conv, "outbound", to_addr='from-1')
        self.msg_helper.make_stored_nack(msg=msg, conv=conv, nack_reason='foo')

        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        [row] = list(reader)
        self.assertEqual(row['network_handover_status'], 'nack')
        self.assertEqual(row['network_handover_reason'], 'foo')

    def test_export_conversation_endpoints(self):
        conv = self.create_conversation(reply_count=0)

        msg = self.msg_helper.make_outbound(
            "outbound", conv=conv, to_addr='from-1')
        msg.set_routing_endpoint('foo')
        self.msg_helper.store_outbound(conv, msg)

        msg = self.msg_helper.make_outbound(
            "inbound", conv=conv, from_addr='from-1')
        msg.set_routing_endpoint('bar')
        self.msg_helper.store_inbound(conv, msg)

        export_conversation_messages_unsorted(conv.user_account.key, conv.key)
        [email] = mail.outbox
        fp = self.get_zipfile_attachment(
            email, 'messages-export.zip', 'messages-export.csv')
        reader = csv.DictReader(fp)
        [row1, row2] = list(reader)
        self.assertEqual(row1['direction'], 'inbound')
        self.assertEqual(row1['endpoint'], 'bar')
        self.assertEqual(row2['direction'], 'outbound')
        self.assertEqual(row2['endpoint'], 'foo')
