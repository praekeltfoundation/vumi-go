# -*- coding: utf-8 -*-

"""Tests for go.apps.multi_surveys.vumi_app"""

import json
import uuid

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis, LogCatcher
from vumi.persist.txriak_manager import TxRiakManager

from go.apps.multi_surveys.vumi_app import MultiSurveyApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import CeleryTestMixIn, DummyConsumerFactory
from go.vumitools.account import AccountStore

from vxpolls.manager import PollManager


def dummy_consumer_factory_factory_factory(publish_func):
    def dummy_consumer_factory_factory():
        dummy_consumer_factory = DummyConsumerFactory()
        dummy_consumer_factory.publish = publish_func
        return dummy_consumer_factory
    return dummy_consumer_factory_factory


class TestMultiSurveyApplication(ApplicationTestCase, CeleryTestMixIn):

    application_class = MultiSurveyApplication
    transport_type = u'sms'
    timeout = 2
    default_polls = {
        0: [{
            'copy': 'Color? 1. Red 2. Blue', 'label': 'color',
            'valid_responses': [u'1', u'2'],
            }],
        1: [{
            'copy': 'Favorite? 1. Foo 2. Bar', 'label': 'favorite',
            'valid_responses': [u'1', u'2'],
            }],
        }
    end_of_survey_copy = {
        0: (u'Thank you!'),
        1: (u"You've done this week's 2 quiz questions. "
            "Please dial *120*646*4*6262# again next week "
            "for new questions. Stay well! Visit askmama.mobi"),
        }

    @inlineCallbacks
    def setUp(self):
        super(TestMultiSurveyApplication, self).setUp()

        self._fake_redis = FakeRedis()
        self.config = {
            'redis_cls': lambda **kw: self._fake_redis,
            'worker_name': 'multi_survey_application',
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
            'worker_names': ['multi_survey_application'],
            }, cls=CommandDispatcher)

        # Setup Celery so that it uses FakeAMQP instead of the real one.
        self.manager = self.app.store.manager  # YOINK!
        self.account_store = AccountStore(self.manager)
        self.VUMI_COMMANDS_CONSUMER = dummy_consumer_factory_factory_factory(
            self.publish_command)
        self.setup_celery_for_tests()

        # Create a test user account
        self.user_account = yield self.account_store.new_user(u'testuser')
        self.user_api = VumiUserApi(self.user_account.key, self.config,
                                        TxRiakManager)

        # Add tags
        self.user_api.api.declare_tags([("pool", "tag1"), ("pool", "tag2")])
        self.user_api.api.set_pool_metadata("pool", {
            "transport_type": self.transport_type,
            "msg_options": {
                "transport_name": self.transport_name,
            },
        })

        # Setup the poll manager
        self.pm = PollManager(self._fake_redis,
                                self.config['vxpolls']['prefix'])

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
    def create_contact(self, name, surname, **kwargs):
        contact = yield self.user_api.contact_store.new_contact(name=name,
            surname=surname, **kwargs)
        yield contact.save()
        returnValue(contact)

    @inlineCallbacks
    def create_conversation(self, conversation_type, subject, message,
        **kwargs):
        conversation = yield self.user_api.new_conversation(
            conversation_type, subject, message, **kwargs)
        yield conversation.save()
        returnValue(self.user_api.wrap_conversation(conversation))

    @inlineCallbacks
    def reply_to(self, msg, content, continue_session=True, **kwargs):
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
            **kwargs)
        yield self.dispatch(reply)

    def create_survey(self, conversation, polls=None, end_response=None):
        # Create a sample survey
        polls = polls or self.default_polls
        poll_id_prefix = 'poll-%s' % (conversation.key,)
        for poll_number, questions in polls.iteritems():
            poll_id = "%s_%d" % (poll_id_prefix, poll_number)
            config = self.pm.get_config(poll_id)
            config.update({
                'poll_id': poll_id,
                'transport_name': self.transport_name,
                'worker_name': 'multi_survey_application',
                'questions': questions,
                })
            config.setdefault('survey_completed_response',
                              (end_response or
                               'Thanks for completing the survey'))
            self.pm.set(poll_id, config)

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
        self._fake_redis.teardown()
        self.pm.stop()
        yield self.app.manager.purge_all()
        yield super(TestMultiSurveyApplication, self).tearDown()

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
        self.assertEqual(msg1['content'], self.default_polls[0][0]['copy'])
        self.assertEqual(msg2['content'], self.default_polls[0][0]['copy'])

    @inlineCallbacks
    def complete_survey(self, polls, start_at=0):
        questions = []
        for poll_number in sorted(polls.keys()):
            questions.extend(polls[poll_number])
            questions.append({
                'copy': self.end_of_survey_copy[poll_number],
                'valid_responses': [u''],
                'session_event': 'close',
                })

        for i, question in enumerate(questions):
            [msg] = yield self.wait_for_messages(1, i + start_at + 1)
            self.assertEqual(msg['content'], question['copy'])
            self.assertEqual(msg['session_event'],
                             question.get('session_event'))
            if i != len(questions) - 1:
                yield self.reply_to(msg, question['valid_responses'][0])

        msgs = self.get_dispatched_messages()[-len(questions):]
        returnValue(msgs)

    @inlineCallbacks
    def test_survey_completion(self):
        yield self.create_contact(u'First', u'Contact',
            msisdn=u'27831234567', groups=[self.group])
        self.create_survey(self.conversation)
        yield self.conversation.start()
        yield self.complete_survey(self.default_polls)

    @inlineCallbacks
    def test_surveys_in_succession(self):
        yield self.create_contact(u'First', u'Contact',
            msisdn=u'27831234567', groups=[self.group])
        self.create_survey(self.conversation)
        yield self.conversation.start()
        start_at = 0
        for i in range(3):
            msgs = yield self.complete_survey(self.default_polls,
                                              start_at=start_at)
            start_at += len(msgs)
            # any input will restart the survey
            yield self.reply_to(msgs[-1], 'hi')
