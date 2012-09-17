from django.conf import settings
from django.contrib.auth.models import User

from go.base.tests.utils import VumiGoDjangoTestCase, declare_longcode_tags
from go.vumitools.tests.utils import CeleryTestMixIn
from go.vumitools.api import VumiApi
from go.base.utils import vumi_api_for_user


class DjangoGoApplicationTestCase(VumiGoDjangoTestCase, CeleryTestMixIn):

    TEST_GROUP_NAME = u"Test Group"
    TEST_CONTACT_NAME = u"Name"
    TEST_CONTACT_SURNAME = u"Surname"
    TEST_SUBJECT = u"Test Conversation"

    def setUp(self):
        super(DjangoGoApplicationTestCase, self).setUp()
        self.setup_api()
        self.declare_longcode_tags()
        self.setup_celery_for_tests()

    def setup_api(self):
        self.api = VumiApi.from_config(settings.VUMI_API_CONFIG)

    def setup_riak_fixtures(self):
        self.user = User.objects.get(username='username')
        self.setup_user_api(self.user)

        # We need a group
        self.group = self.contact_store.new_group(self.TEST_GROUP_NAME)
        self.group_key = self.group.key

        # Also a contact
        self.contact = self.contact_store.new_contact(
            name=self.TEST_CONTACT_NAME, surname=self.TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        self.contact.add_to_group(self.group)
        self.contact.save()
        self.contact_key = self.contact.key

        # And a conversation
        self.conversation = self.conv_store.new_conversation(
            conversation_type=u'bulk_message', subject=self.TEST_SUBJECT,
            message=u"Test message", delivery_class=u"sms",
            delivery_tag_pool=u"longcode", groups=[self.group_key])
        self.conv_key = self.conversation.key

    def mkconversation(self, **kwargs):
        defaults = {
            'conversation_type': u'bulk_message',
            'subject': u'subject',
            'message': u'hello world'
        }
        defaults.update(kwargs)
        return self.conv_store.new_conversation(**defaults)

    def mkcontact(self, name=None, surname=None, msisdn=u'+1234567890',
                  **kwargs):
        return self.contact_store.new_contact(
            name=unicode(name or self.TEST_CONTACT_NAME),
            surname=unicode(surname or self.TEST_CONTACT_SURNAME),
            msisdn=unicode(msisdn), **kwargs)

    def setup_user_api(self, django_user):
        self.user_api = vumi_api_for_user(django_user)
        self.contact_store = self.user_api.contact_store
        self.contact_store.contacts.enable_search()
        self.contact_store.groups.enable_search()
        self.conv_store = self.user_api.conversation_store

    def declare_longcode_tags(self):
        declare_longcode_tags(self.api)

    def acquire_all_longcode_tags(self):
        for _i in range(4):
            self.api.acquire_tag("longcode")

    def get_api_commands_sent(self):
        consumer = self.get_cmd_consumer()
        return self.fetch_cmds(consumer)

    def get_contacts_for_conversation(self, conversation):
        return self.contact_store.get_contacts_for_conversation(conversation)
