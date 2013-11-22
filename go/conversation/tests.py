import json
import logging
from datetime import date
from StringIO import StringIO
from zipfile import ZipFile

from mock import patch
from django import forms
from django.core import mail
from django.core.urlresolvers import reverse
from django.utils.unittest import skip

import go.base.utils
from go.base.tests.utils import (
    VumiGoDjangoTestCase, FakeMessageStoreClient, FakeMatchResult)
from go.conversation.templatetags import conversation_tags
from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)
from go.vumitools.api import VumiApiCommand
from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)
from go.vumitools.conversation.utils import ConversationWrapper
from go.dashboard import Dashboard, DashboardLayout, DashboardParseError
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


class BaseConversationViewTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(BaseConversationViewTestCase, self).setUp()
        self.monkey_patch(
            go.base.utils, 'get_conversation_pkg', self._get_conversation_pkg)
        self.patch_config(VUMI_INSTALLED_APPS=DUMMY_CONVERSATION_SETTINGS)
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

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
        self.assertNotContains(response, u'My Conversation')

        self.create_conversation(
            name=u'My Conversation', conversation_type=u'dummy')
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, u'My Conversation')

    def test_index_search(self):
        """Filter conversations based on query string"""
        conv = self.create_conversation(conversation_type=u'dummy')

        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, conv.name)

        response = self.client.get(reverse('conversations:index'), {
            'query': 'something that does not exist in the fixtures'})
        self.assertNotContains(response, conv.name)

    def test_index_search_on_type(self):
        conv = self.create_conversation(conversation_type=u'dummy')
        self.add_app_permission(u'gotest.dummy')
        self.add_app_permission(u'gotest.with_actions')

        def search(conversation_type):
            return self.client.get(reverse('conversations:index'), {
                'query': conv.name,
                'conversation_type': conversation_type,
            })

        self.assertContains(search('dummy'), conv.key)
        self.assertNotContains(search('with_actions'), conv.key)

    def test_index_search_on_status(self):
        conv = self.create_conversation(conversation_type=u'dummy')

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
        conv = self.user_api.get_wrapped_conversation(conv.key)
        conv.set_status_started()
        conv.save()
        self.assertNotContains(search('draft'), conv.key)
        self.assertContains(search('running'), conv.key)
        self.assertNotContains(search('finished'), conv.key)

        # Set the status to `stopped' again
        conv = self.user_api.get_wrapped_conversation(conv.key)
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
            conv = self.create_conversation(conversation_type=u'dummy')
        response = self.client.get(reverse('conversations:index'))
        # CONVERSATIONS_PER_PAGE = 12
        self.assertContains(response, conv.name, count=12)
        response = self.client.get(reverse('conversations:index'), {'p': 2})
        self.assertContains(response, conv.name, count=1)

    def test_pagination_with_query_and_type(self):
        self.add_app_permission(u'gotest.dummy')
        self.add_app_permission(u'gotest.with_actions')
        for i in range(13):
            conv = self.create_conversation(conversation_type=u'dummy')
        response = self.client.get(reverse('conversations:index'), {
            'query': conv.name,
            'p': 2,
            'conversation_type': 'dummy',
            'conversation_status': 'draft',
        })

        self.assertNotContains(response, '?p=2')


class TestNewConversationView(BaseConversationViewTestCase):
    def test_get_new_conversation(self):
        self.add_app_permission(u'gotest.dummy')
        response = self.client.get(reverse('conversations:new_conversation'))
        self.assertContains(response, 'Conversation name')
        self.assertContains(response, 'kind of conversation')
        self.assertContains(response, 'dummy')
        self.assertNotContains(response, 'with_actions')

    def test_post_new_conversation(self):
        self.add_app_permission(u'gotest.dummy')
        conv_data = {
            'name': 'new conv',
            'conversation_type': 'dummy',
        }
        response = self.client.post(
            reverse('conversations:new_conversation'), conv_data)
        [conv] = self.user_api.active_conversations()
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        self.assertEqual(conv.name, 'new conv')
        self.assertEqual(conv.conversation_type, 'dummy')

    def test_post_new_conversation_extra_endpoints(self):
        self.add_app_permission(u'gotest.extra_endpoints')
        conv_data = {
            'name': 'new conv',
            'conversation_type': 'extra_endpoints',
        }
        response = self.client.post(reverse('conversations:new_conversation'),
                                    conv_data)
        [conv] = self.user_api.active_conversations()
        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})
        self.assertRedirects(response, show_url)
        self.assertEqual(conv.name, 'new conv')
        self.assertEqual(conv.conversation_type, 'extra_endpoints')
        self.assertEqual(list(conv.extra_endpoints), [u'extra'])


class TestConversationViews(BaseConversationViewTestCase):
    def test_show_no_content_block(self):
        conv = self.create_conversation(conversation_type=u'dummy')
        show_url = self.get_view_url(conv, 'show')
        response = self.client.get(show_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Content')
        self.assertNotContains(response, show_url + 'edit/')

    def test_show_editable(self):
        conv = self.create_conversation(conversation_type=u'simple_edit')
        response = self.client.get(self.get_view_url(conv, 'show'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Content')
        self.assertContains(response, self.get_view_url(conv, 'edit'))

    def test_edit_simple(self):
        conv = self.create_conversation(conversation_type=u'simple_edit')
        self.assertEqual(conv.config, {})

        response = self.client.get(self.get_view_url(conv, 'edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'simple_field')
        self.assertNotContains(response, 'field value')

        response = self.client.post(self.get_view_url(conv, 'edit'), {
            'simple_field': ['field value'],
        })
        self.assertRedirects(response, self.get_view_url(conv, 'show'))
        conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertEqual(conv.config, {'simple_field': 'field value'})

        response = self.client.get(self.get_view_url(conv, 'edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'simple_field')
        self.assertContains(response, 'field value')

    def test_edit_complex(self):
        conv = self.create_conversation(conversation_type=u'complex_edit')
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
        conv = self.user_api.get_wrapped_conversation(conv.key)
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

    def test_edit_conversation_details(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', name=u'test', description=u'test')

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
        reloaded_conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertEqual(reloaded_conv.name, 'foo')
        self.assertEqual(reloaded_conv.description, 'bar')

    def test_conversation_contact_group_listing(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', name=u'test', description=u'test')
        group1 = self.user_api.contact_store.new_group(u'Contact Group 1')
        group2 = self.user_api.contact_store.new_group(u'Contact Group 2')

        conv.add_group(group1)
        conv.save()

        show_url = reverse('conversations:conversation', kwargs={
            'conversation_key': conv.key, 'path_suffix': ''})

        resp = self.client.get(show_url)
        self.assertContains(resp, group1.name)
        self.assertNotContains(resp, group2.name)

    def test_conversation_render_contact_group_edit(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', name=u'test', description=u'test')
        group1 = self.user_api.contact_store.new_group(u'Contact Group 1')
        group2 = self.user_api.contact_store.new_group(u'Contact Group 2')

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
        conv = self.create_conversation(
            conversation_type=u'dummy', name=u'test', description=u'test')
        self.user_api.contact_store.new_group(u'Contact Group 1')
        group2 = self.user_api.contact_store.new_group(u'Contact Group 2')
        group3 = self.user_api.contact_store.new_group(u'Contact Group 3')

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
        conv = self.create_conversation(conversation_type=u'dummy')

        response = self.client.post(
            self.get_view_url(conv, 'start'), follow=True)
        self.assertRedirects(response, self.get_view_url(conv, 'show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Dummy Conversation started")

        conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertTrue(conv.starting())
        [start_cmd] = self.get_api_commands_sent()
        self.assertEqual(start_cmd, VumiApiCommand.command(
            '%s_application' % (conv.conversation_type,), 'start',
            user_account_key=conv.user_account.key, conversation_key=conv.key))

    def test_stop(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)

        response = self.client.post(
            self.get_view_url(conv, 'stop'), follow=True)
        self.assertRedirects(response, self.get_view_url(conv, 'show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Dummy Conversation stopped")

        conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertTrue(conv.stopping())

    def test_aggregates(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        # Inbound only
        self.add_messages_to_conv(
            5, conv, start_date=date(2012, 1, 1), time_multiplier=12)
        # Inbound and outbound
        self.add_messages_to_conv(
            5, conv, start_date=date(2013, 1, 1), time_multiplier=12,
            reply=True)
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

    def test_export_messages(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        self.add_messages_to_conv(
            5, conv, start_date=date(2012, 1, 1), time_multiplier=12,
            reply=True)
        response = self.client.post(self.get_view_url(conv, 'message_list'), {
            '_export_conversation_messages': True,
        })
        self.assertRedirects(response, self.get_view_url(conv, 'message_list'))
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertTrue(conv.name in email.subject)
        self.assertTrue(conv.name in email.body)
        [(file_name, zipcontent, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')
        zipfile = ZipFile(StringIO(zipcontent), 'r')
        content = zipfile.open('messages-export.csv', 'r').read()
        # 1 header, 5 sent, 5 received, 1 trailing newline == 12
        self.assertEqual(12, len(content.split('\n')))
        self.assertEqual(mime_type, 'application/zip')

    def test_message_list_pagination(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        # Create 21 inbound & 21 outbound messages, since we have
        # 20 messages per page it should give us 2 pages
        self.add_messages_to_conv(21, conv)
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
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        msgs = self.add_messages_to_conv(10, conv, reply=True)
        replies = [reply for _msg, reply in msgs]
        for msg in replies[:4]:
            self.ack_message(msg)
        for msg in replies[4:9]:
            self.nack_message(msg)
        for msg in replies[:2]:
            self.delivery_report_on_message(msg, status='delivered')
        for msg in replies[2:5]:
            self.delivery_report_on_message(msg, status='pending')
        for msg in replies[5:9]:
            self.delivery_report_on_message(msg, status='failed')

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

    def test_message_list_no_sensitive_msgs(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)

        def assert_messages(count):
            r_in = self.client.get(
                self.get_view_url(conv, 'message_list'),
                {'direction': 'inbound'})
            self.assertContains(r_in, 'from-addr', count)
            r_out = self.client.get(
                self.get_view_url(conv, 'message_list'),
                {'direction': 'outbound'})
            self.assertContains(r_out, 'from-addr', count)

        assert_messages(0)
        self.add_message_to_conv(conv, reply=True)
        assert_messages(1)
        self.add_message_to_conv(conv, reply=True, sensitive=True)
        assert_messages(1)
        self.add_message_to_conv(conv, reply=True)
        assert_messages(2)

    def test_message_list_with_bad_transport_type_inbound(self):
        # inbound messages could have an unsupported transport_type
        # if the transport sent something we don't yet support
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)

        self.add_message_to_conv(conv, transport_type="bad horse")

        r_in = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'inbound'})

        self.assertContains(r_in, 'from-addr', 1)
        self.assertContains(r_in, 'bad horse (unsupported)', 1)

    def test_message_list_with_bad_transport_type_outbound(self):
        # unsent message don't have their transport type set to something
        # that a contact can be created for
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)

        self.add_message_to_conv(conv, reply=True, transport_type="bad horse")

        r_out = self.client.get(
            self.get_view_url(conv, 'message_list'),
            {'direction': 'outbound'})

        self.assertContains(r_out, 'from-addr', 1)
        self.assertContains(r_out, 'bad horse (unsupported)', 1)

    def test_reply_on_inbound_messages_only(self):
        # Fake the routing setup.
        self.monkey_patch(
            ConversationWrapper, 'has_channel_supporting_generic_sends',
            lambda s: True)
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        messages = self.add_messages_to_conv(1, conv, reply=True)
        [msg_in, msg_out] = messages[0]

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
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        self.add_messages_to_conv(1, conv)

        response = self.client.get(
            self.get_view_url(conv, 'message_list'), {'direction': 'inbound'})
        self.assertNotContains(response, 'Reply')

    def test_send_one_off_reply(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        self.add_messages_to_conv(1, conv)
        [msg] = conv.received_messages()
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

    @skip("The new views don't have this.")
    def test_show_cached_message_overview(self):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        self.add_messages_to_conv(10, conv)
        response = self.client.get(self.get_view_url(conv, 'show'))
        self.assertContains(response,
            '10 sent for delivery to the networks.')
        self.assertContains(response,
            '10 accepted for delivery by the networks.')
        self.assertContains(response, '10 delivered.')

    @skip("The new views don't have this.")
    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_search(self, Client, MatchResult):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult()
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        response = self.client.get(self.get_view_url(conv, 'message_list'), {
            'q': 'hello world 1',
        })

        template_names = [t.name for t in response.templates]
        self.assertTrue(
            'generic/includes/message-load-results.html' in template_names)
        self.assertEqual(response.context['token'], fake_client.token)

    @skip("The new views don't have this.")
    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_results(self, Client, MatchResult):
        conv = self.create_conversation(
            conversation_type=u'dummy', started=True)
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult(tries=2,
            results=[self.mkmsg_out() for i in range(10)])
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        fetch_results_url = self.get_view_url(conv, 'message_search_result')
        fetch_results_params = {
            'q': 'hello world 1',
            'batch_id': 'batch-id',
            'direction': 'inbound',
            'token': fake_client.token,
            'delay': 100,
        }

        response1 = self.client.get(fetch_results_url, fetch_results_params)
        response2 = self.client.get(fetch_results_url, fetch_results_params)

        # First time it should still show the loading page
        self.assertTrue('generic/includes/message-load-results.html' in
                        [t.name for t in response1.templates])
        self.assertEqual(response1.context['delay'], 1.1 * 100)
        # Second time it should still render the messages
        self.assertTrue('generic/includes/message-list.html' in
                        [t.name for t in response2.templates])
        self.assertEqual(response1.context['token'], fake_client.token)
        # Second time we should list the matching messages
        self.assertEqual(response2.context['token'], fake_client.token)
        self.assertEqual(
            len(response2.context['message_page'].object_list), 10)


class TestConversationTemplateTags(BaseConversationViewTestCase):
    def _assert_cs_url(self, suffix, conv, view_name=None):
        expected = '/conversations/%s/%s' % (conv.key, suffix)
        if view_name is None:
            result = conversation_tags.conversation_screen(conv)
        else:
            result = conversation_tags.conversation_screen(conv, view_name)
        self.assertEqual(expected, result)

    def test_conversation_screen_tag(self):
        conv = self.create_conversation(conversation_type=u'dummy')
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
        conv = self.create_conversation(conversation_type=u'with_actions')
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


class TestConversationDashboardView(BaseConversationViewTestCase):
    def setUp(self):
        super(TestConversationDashboardView, self).setUp()
        self.diamondash_api = FakeDiamondashApiClient()

        self.error_log = []
        logger = logging.getLogger('go.conversation.view_definition')

        def log_error(e):
            self.error_log.append(unicode(e))

        self.monkey_patch(logger, 'error', log_error)
        self.monkey_patch(Dashboard, 'api_client', self.diamondash_api)

    def tearDown(self):
        super(TestConversationDashboardView, self).tearDown()

    def test_get_dashboard(self):
        self.diamondash_api.set_response({'happy': 'dashboard'})

        conv = self.create_conversation(conversation_type=u'dummy')
        response = self.client.get(
            self.get_view_url(conv, 'conversation_dashboard'))

        [dd_request] = self.diamondash_api.get_requests()
        raw_dashboard = dd_request['data']
        self.assertEqual(raw_dashboard['name'], conv.key)
        self.assertEqual(raw_dashboard['title'], conv.name)
        self.assertTrue('widgets' in raw_dashboard)

        self.assertEqual(
            json.loads(response.context['model_data']),
            {'happy': 'dashboard'})

    def test_get_dashboard_for_sync_error_handling(self):
        self.diamondash_api.set_error_response(400, ':(')

        conv = self.create_conversation(conversation_type=u'dummy')
        response = self.client.get(
            self.get_view_url(conv, 'conversation_dashboard'))

        self.assertEqual(
            self.error_log,
            ['Dashboard sync failed: '
             '(400) {"message": ":(", "success": false}'])

        self.assertEqual(json.loads(response.context['model_data']), None)

    def test_get_dashboard_for_parse_error_handling(self):
        def bad_add_entity(*a, **kw):
            raise DashboardParseError(':(')

        self.monkey_patch(DashboardLayout, 'add_entity', bad_add_entity)
        conv = self.create_conversation(conversation_type=u'dummy')

        response = self.client.get(
            self.get_view_url(conv, 'conversation_dashboard'))
        self.assertEqual(self.error_log, [':('])
        self.assertEqual(json.loads(response.context['model_data']), None)
