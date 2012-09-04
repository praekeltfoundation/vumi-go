"""Tests for go.apps.sequential_send.vumi_app"""

import uuid

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import Clock

from vumi.message import TransportUserMessage

from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.sequential_send.vumi_app import SequentialSendApplication


class TestSequentialSendApplication(AppWorkerTestCase):

    application_class = SequentialSendApplication
    transport_type = u'sms'

    @inlineCallbacks
    def setUp(self):
        super(TestSequentialSendApplication, self).setUp()

        # Setup the SurveyApplication
        self.app = yield self.get_application({
                'worker_name': 'sequential_send_application',
                }, start=False)
        self.clock = self.app._clock = Clock()
        yield self.app.startWorker()

        # Setup the command dispatcher so we cand send it commands
        self.cmd_dispatcher = yield self.get_application({
                'transport_name': 'cmd_dispatcher',
                'worker_names': ['sequential_send_application'],
                }, cls=CommandDispatcher)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!
        self._persist_riak_managers.append(self.vumi_api.manager)

        # Create a test user account
        self.user_account = yield self.vumi_api.account_store.new_user(
            u'testuser')
        self.user_api = VumiUserApi(self.vumi_api, self.user_account.key)

        # Add tags
        self.user_api.api.declare_tags([("pool", "tag1"), ("pool", "tag2")])
        self.user_api.api.set_pool_metadata("pool", {
            "transport_type": self.transport_type,
            "msg_options": {
                "transport_name": self.transport_name,
            },
        })

        # Give a user access to a tagpool
        self.user_api.api.account_store.tag_permissions(uuid.uuid4().hex,
            tagpool=u"pool", max_keys=None)

        # Create a group and a conversation
        self.group = yield self.create_group(u'test group')

        self.conversation = yield self.create_conversation(u'multi_survey',
            u'Subject', u'Message',
            delivery_tag_pool=u'pool',
            delivery_class=self.transport_type)
        self.conversation.add_group(self.group)
        yield self.conversation.save()

    @inlineCallbacks
    def create_group(self, name):
        group = yield self.user_api.contact_store.new_group(name)
        yield group.save()
        returnValue(group)

    @inlineCallbacks
    def create_contact(self, name, surname, **kw):
        contact = yield self.user_api.contact_store.new_contact(name=name,
            surname=surname, **kw)
        yield contact.save()
        returnValue(contact)

    @inlineCallbacks
    def create_conversation(self, conversation_type, subject, message, **kw):
        conversation = yield self.user_api.new_conversation(
            conversation_type, subject, message, **kw)
        yield conversation.save()
        returnValue(self.user_api.wrap_conversation(conversation))

    @inlineCallbacks
    def reply_to(self, msg, content, continue_session=True, **kw):
        session_event = (None if continue_session
                            else TransportUserMessage.SESSION_CLOSE)
        reply = TransportUserMessage(
            to_addr=msg['from_addr'],
            from_addr=msg['to_addr'],
            group=msg['group'],
            in_reply_to=msg['message_id'],
            content=content,
            session_event=session_event,
            transport_name=msg['transport_name'],
            transport_type=msg['transport_type'],
            transport_metadata=msg['transport_metadata'],
            helper_metadata=msg['helper_metadata'],
            **kw)
        yield self.dispatch(reply)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.wait_for_dispatched_messages(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def test_start(self):
        self.contact1 = yield self.create_contact(name=u'First',
            surname=u'Contact', msisdn=u'27831234567', groups=[self.group])
        self.contact2 = yield self.create_contact(name=u'Second',
            surname=u'Contact', msisdn=u'27831234568', groups=[self.group])

        yield self.conversation.start()
        self.clock.advance(70)
        self.clock.advance(70)
        self.clock.advance(70)
        self.clock.advance(70)

        # [msg1, msg2] = (yield self.wait_for_dispatched_messages(2))
        # self.assertEqual(msg1['content'], self.default_polls[0][0]['copy'])
        # self.assertEqual(msg2['content'], self.default_polls[0][0]['copy'])
