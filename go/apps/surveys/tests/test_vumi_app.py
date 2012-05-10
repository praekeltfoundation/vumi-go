# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

import json
import uuid

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent, TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis, LogCatcher
from vumi.persist.txriak_manager import TxRiakManager

from go.apps.surveys.vumi_app import SurveyApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import CeleryTestMixIn, DummyConsumerFactory
from go.vumitools.account import AccountStore

from vxpolls.manager import PollManager

from twisted.internet.base import DelayedCall
DelayedCall.debug = True


def dummy_consumer_factory_factory_factory(publish_func):
    def dummy_consumer_factory_factory():
        dummy_consumer_factory = DummyConsumerFactory()
        dummy_consumer_factory.publish = publish_func
        return dummy_consumer_factory
    return dummy_consumer_factory_factory


class TestSurveyApplication(ApplicationTestCase, CeleryTestMixIn):

    application_class = SurveyApplication
    transport_type = 'sms'
    timeout = 2
    default_questions = [{
        'copy': 'What is your favorite color? 1. Red 2. Yellow '
                '3. Blue',
        'label': 'favorite color',
        'valid_responses': [1, 2, 3],
    }, {
        'checks': {
            'equal': {'favorite color': 1}
        },
        'copy': 'What shade of red? 1. Dark or 2. Light',
        'label': 'what shade',
        'valid_responses': [1, 2],
    }, {
        'copy': 'What is your favorite fruit? 1. Apples 2. Oranges '
                '3. Bananas',
        'label': 'favorite fruit',
        'valid_responses': [1, 2, 3],
    }, {
        'copy': 'What is your favorite editor? 1. Vim 2. Emacs '
                '3. Other',
        'valid_responses': [1, 2, 3]
    }]

    @inlineCallbacks
    def setUp(self):
        super(TestSurveyApplication, self).setUp()

        self._fake_redis = FakeRedis()
        self.config = {
            'redis_cls': lambda **kw: self._fake_redis,
            'poll_id': '1',
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

        # Create a group, contacts and a conversation
        self.group = yield self.user_api.contact_store.new_group(u'test group')
        yield self.group.save()
        self.contact1 = yield self.user_api.contact_store.new_contact(
            u'First', u'Contact', msisdn=u'27831234567', groups=[self.group])
        yield self.contact1.save()
        self.contact2 = yield self.user_api.contact_store.new_contact(
            u'Second', u'Contact', msisdn=u'27831234568', groups=[self.group])
        yield self.contact2.save()
        conversation = yield self.user_api.new_conversation(
            u'survey', u'Subject', u'Message', delivery_tag_pool=u"pool",
            delivery_class=u'sms')
        conversation.add_group(self.group)
        yield conversation.save()
        self.conversation = self.user_api.wrap_conversation(conversation)

    def create_survey(self, conversation, questions=None):
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
                        'Thanks for completing the survey')
        self.pm.set(poll_id, config)
        return self.pm.get(poll_id)

    def publish_command(self, cmd_dict):
        data = json.dumps(cmd_dict)
        self._amqp.publish_raw('vumi', 'vumi.api', data)

    @inlineCallbacks
    def tearDown(self):
        self.restore_celery()
        self._fake_redis.teardown()
        self.pm.stop()
        yield self.app.manager.purge_all()
        yield super(TestSurveyApplication, self).tearDown()

    @inlineCallbacks
    def test_start(self):
        self.create_survey(self.conversation)
        with LogCatcher() as log:
            yield self.conversation.start()
            self.assertEqual(log.errors, [])

        [msg1, msg2] = (yield self.wait_for_dispatched_messages(2))
        self.assertEqual(msg1['content'], self.default_questions[0]['copy'])
        self.assertEqual(msg2['content'], self.default_questions[0]['copy'])
