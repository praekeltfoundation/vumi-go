# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

import json
import uuid

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.persist.txredis_manager import TxRedisManager
from vumi.tests.utils import LogCatcher

from go.apps.surveys.vumi_app import SurveyApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import CeleryTestMixIn, DummyConsumerFactory
from go.vumitools.account import AccountStore


def dummy_consumer_factory_factory_factory(publish_func):
    def dummy_consumer_factory_factory():
        dummy_consumer_factory = DummyConsumerFactory()
        dummy_consumer_factory.publish = publish_func
        return dummy_consumer_factory
    return dummy_consumer_factory_factory


class TestSurveyApplication(ApplicationTestCase, CeleryTestMixIn):

    application_class = SurveyApplication
    transport_type = u'sms'
    default_questions = [{
        'copy': 'What is your favorite color? 1. Red 2. Yellow '
                '3. Blue',
        'label': 'favorite color',
        'valid_responses': [u'1', u'2', u'3'],
    }, {
        'checks': {
            'equal': {'favorite color': u'1'}
        },
        'copy': 'What shade of red? 1. Dark or 2. Light',
        'label': 'what shade',
        'valid_responses': [u'1', u'2'],
    }, {
        'copy': 'What is your favorite fruit? 1. Apples 2. Oranges '
                '3. Bananas',
        'label': 'favorite fruit',
        'valid_responses': [u'1', u'2', u'3'],
    }, {
        'copy': 'What is your favorite editor? 1. Vim 2. Emacs '
                '3. Other',
        'valid_responses': [u'1', u'2', u'3']
    }]

    @inlineCallbacks
    def setUp(self):
        super(TestSurveyApplication, self).setUp()

        self.redis = yield TxRedisManager.from_config('FAKE_REDIS')
        self.config = {
            'redis': self.redis._client,
            'worker_name': 'survey_application',
            'message_store': {
                'store_prefix': 'test.',
            },
            'riak_manager': {
                'bucket_prefix': 'test.',
            },
            'vxpolls': {
                'prefix': 'test.',
            }
        }

        # Setup the SurveyApplication
        self.app = yield self.get_application(self.config)

        # Setup the command dispatcher so we cand send it commands
        self.cmd_dispatcher = yield self.get_application({
            'transport_name': 'cmd_dispatcher',
            'worker_names': ['survey_application'],
            }, cls=CommandDispatcher)

        # Setup Celery so that it uses FakeAMQP instead of the real one.
        self.manager = self.app.store.manager  # YOINK!
        self.account_store = AccountStore(self.manager)
        self.VUMI_COMMANDS_CONSUMER = dummy_consumer_factory_factory_factory(
            self.publish_command)
        self.setup_celery_for_tests()

        # Create a test user account
        self.user_account = yield self.account_store.new_user(u'testuser')
        self.user_api = yield VumiUserApi.from_config_async(
            self.user_account.key, self.config)

        # Add tags
        self.user_api.api.declare_tags([("pool", "tag1"), ("pool", "tag2")])
        self.user_api.api.set_pool_metadata("pool", {
            "transport_type": self.transport_type,
            "msg_options": {
                "transport_name": self.transport_name,
            },
        })

        # Setup the poll manager
        self.pm = self.app.pm

        # Give a user access to a tagpool
        self.user_api.api.account_store.tag_permissions(uuid.uuid4().hex,
            tagpool=u"pool", max_keys=None)

        # Create a group and a conversation
        self.group = yield self.create_group(u'test group')

        self.conversation = yield self.create_conversation(u'survey',
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

    def create_survey(self, conversation, questions=None, end_response=None):
        # Create a sample survey
        questions = questions or self.default_questions
        poll_id = 'poll-%s' % (conversation.key,)
        config = self.pm.get_config(poll_id)
        config.update({
            'poll_id': poll_id,
            'transport_name': self.transport_name,
            'worker_name': 'survey_application',
            'questions': questions
        })

        config.setdefault('survey_completed_response',
            (end_response or 'Thanks for completing the survey'))
        self.pm.set(poll_id, config)
        return self.pm.get(poll_id)

    def publish_command(self, cmd_dict):
        data = json.dumps(cmd_dict)
        self._amqp.publish_raw('vumi', 'vumi.api', data)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.wait_for_dispatched_messages(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def tearDown(self):
        self.restore_celery()
        yield self.redis._close()
        self.pm.stop()
        yield self.app.manager.purge_all()
        yield super(TestSurveyApplication, self).tearDown()

    @inlineCallbacks
    def test_start(self):
        self.contact1 = yield self.create_contact(name=u'First',
            surname=u'Contact', msisdn=u'27831234567', groups=[self.group])
        self.contact2 = yield self.create_contact(name=u'Second',
            surname=u'Contact', msisdn=u'27831234568', groups=[self.group])
        self.create_survey(self.conversation)
        with LogCatcher() as log:
            yield self.conversation.start()
            self.assertEqual(log.errors, [])

        [msg1, msg2] = (yield self.wait_for_dispatched_messages(2))
        self.assertEqual(msg1['content'], self.default_questions[0]['copy'])
        self.assertEqual(msg2['content'], self.default_questions[0]['copy'])

    @inlineCallbacks
    def complete_survey(self, questions, start_at=0):
        for i in range(len(questions)):
            [msg] = yield self.wait_for_messages(1, i + start_at + 1)
            self.assertEqual(msg['content'], questions[i]['copy'])
            response = str(questions[i]['valid_responses'][0])
            yield self.reply_to(msg, response)

        nr_of_messages = 1 + len(questions) + start_at
        all_messages = yield self.wait_for_dispatched_messages(nr_of_messages)
        last_msg = all_messages[-1]
        self.assertEqual(last_msg['content'],
            'Thanks for completing the survey')
        self.assertEqual(last_msg['session_event'],
            TransportUserMessage.SESSION_CLOSE)
        returnValue(last_msg)

    @inlineCallbacks
    def test_survey_completion(self):
        yield self.create_contact(u'First', u'Contact',
            msisdn=u'27831234567', groups=[self.group])
        self.create_survey(self.conversation)
        yield self.conversation.start()
        yield self.complete_survey(self.default_questions)
