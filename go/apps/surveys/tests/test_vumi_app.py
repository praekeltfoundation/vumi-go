# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

import uuid
import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.tests.utils import LogCatcher

from go.apps.surveys.vumi_app import SurveyApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import AppWorkerTestCase


class TestSurveyApplication(AppWorkerTestCase):

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

        # Setup the SurveyApplication
        self.app = yield self.get_application({
                'worker_name': 'survey_application',
                'vxpolls': {'prefix': 'test.'},
                })

        # Setup the command dispatcher so we cand send it commands
        self.cmd_dispatcher = yield self.get_application({
            'transport_name': 'cmd_dispatcher',
            'worker_names': ['survey_application'],
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
        returnValue(reply)

    @inlineCallbacks
    def create_survey(self, conversation, questions=None, end_response=None):
        # Create a sample survey
        questions = questions or self.default_questions
        poll_id = 'poll-%s' % (conversation.key,)
        config = yield self.pm.get_config(poll_id)
        config.update({
            'poll_id': poll_id,
            'transport_name': self.transport_name,
            'worker_name': 'survey_application',
            'questions': questions
        })

        config.setdefault('survey_completed_response',
            (end_response or 'Thanks for completing the survey'))
        yield self.pm.set(poll_id, config)
        poll = yield self.pm.get(poll_id)
        returnValue(poll)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.wait_for_dispatched_messages(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def tearDown(self):
        self.pm.stop()
        yield super(TestSurveyApplication, self).tearDown()

    @inlineCallbacks
    def test_start(self):
        self.contact1 = yield self.create_contact(name=u'First',
            surname=u'Contact', msisdn=u'27831234567', groups=[self.group])
        self.contact2 = yield self.create_contact(name=u'Second',
            surname=u'Contact', msisdn=u'27831234568', groups=[self.group])
        yield self.create_survey(self.conversation)
        with LogCatcher() as log:
            yield self.conversation.start()
            self.assertEqual(log.errors, [])

        [msg1, msg2] = (yield self.wait_for_dispatched_messages(2))
        self.assertEqual(msg1['content'], self.default_questions[0]['copy'])
        self.assertEqual(msg2['content'], self.default_questions[0]['copy'])

    def _reformat_participant_for_comparison(self, participant):
        clone = participant.copy()
        clone['labels'] = json.loads(participant['labels'])
        clone['polls'] = json.loads(participant['polls'])
        clone['updated_at'] = int(participant['updated_at'])
        return clone

    @inlineCallbacks
    def complete_survey(self, questions, start_at=0):
        for i in range(len(questions)):
            [msg] = yield self.wait_for_messages(1, i + start_at + 1)
            self.assertEqual(msg['content'], questions[i]['copy'])
            response = str(questions[i]['valid_responses'][0])
            last_sent_msg = yield self.reply_to(msg, response)

        nr_of_messages = 1 + len(questions) + start_at
        all_messages = yield self.wait_for_dispatched_messages(nr_of_messages)
        last_msg = all_messages[-1]
        self.assertEqual(last_msg['content'],
            'Thanks for completing the survey')
        self.assertEqual(last_msg['session_event'],
            TransportUserMessage.SESSION_CLOSE)

        poll_id = 'poll-%s' % (self.conversation.key,)

        [app_event] = self.get_dispatched_app_events()

        # The poll has been completed and so the results have been
        # archived, get the participant from the archive
        [participant] = (yield self.pm.get_archive(poll_id,
            last_sent_msg['from_addr']))

        self.assertEqual(app_event['account_key'], self.user_account.key)
        self.assertEqual(app_event['conversation_key'], self.conversation.key)

        # make sure we have a participant, pop it out and
        # compare with expected result further down.
        event_participant = app_event['content'].pop('participant')
        self.assertTrue(event_participant)

        self.assertEqual(app_event['content'], {
            'from_addr': last_sent_msg['from_addr'],
            'transport_type': last_sent_msg['transport_type'],
            'message_id': last_sent_msg['message_id'],
        })

        self.assertEqual(
            self._reformat_participant_for_comparison(event_participant),
            self._reformat_participant_for_comparison(participant.dump()))

        returnValue(last_msg)

    @inlineCallbacks
    def test_survey_completion(self):
        yield self.create_contact(u'First', u'Contact',
            msisdn=u'27831234567', groups=[self.group])
        yield self.create_survey(self.conversation)
        yield self.conversation.start()
        yield self.complete_survey(self.default_questions)
