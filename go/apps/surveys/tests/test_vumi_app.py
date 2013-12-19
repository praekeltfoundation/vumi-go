# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.tests.helpers import VumiTestCase

from go.apps.surveys.vumi_app import SurveyApplication
from go.apps.tests.helpers import AppWorkerHelper
from go.vumitools.api import VumiApiCommand


class TestSurveyApplication(VumiTestCase):

    default_questions = [{
        'copy': 'What is your favorite color? 1. Red 2. Yellow '
                '3. Blue',
        'label': 'favorite color',
        'valid_responses': [u'1', u'2', u'3'],
    }, {
        'checks': [
            ['equal', 'favorite color', u'1'],
        ],
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
        'label': 'editor',
        'valid_responses': [u'1', u'2', u'3']
    }]

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(AppWorkerHelper(SurveyApplication))
        self.app = yield self.app_helper.get_app_worker({
            'vxpolls': {'prefix': 'test.'},
        })
        self.pm = self.app.pm

        self.group = yield self.app_helper.create_group(u'test group')
        self.conversation = yield self.app_helper.create_conversation(
            groups=[self.group])

    def reply_to(self, msg, content, **kw):
        return self.app_helper.make_dispatch_inbound(
            content, to_addr=msg['from_addr'], from_addr=msg['to_addr'],
            conv=self.conversation, **kw)

    @inlineCallbacks
    def create_survey(self, conversation, questions=None, end_response=None):
        # Create a sample survey
        questions = questions or self.default_questions
        poll_id = 'poll-%s' % (conversation.key,)
        config = yield self.pm.get_config(poll_id)
        config.update({
            'poll_id': poll_id,
            'questions': questions
        })

        config.setdefault('survey_completed_response',
            (end_response or 'Thanks for completing the survey'))
        yield self.pm.set(poll_id, config)
        poll = yield self.pm.get(poll_id)
        returnValue(poll)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.app_helper.wait_for_dispatched_outbound(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def send_send_survey_command(self, conversation):
        batch_id = self.conversation.batch.key
        yield self.app_helper.dispatch_command(
            "send_survey",
            user_account_key=self.conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            msg_options={},
            delivery_class=conversation.delivery_class,
        )

    @inlineCallbacks
    def test_clearing_old_survey_data(self):
        contact = yield self.app_helper.create_contact(
            u'+27831234567', name=u'First', surname=u'Contact',
            groups=[self.group])
        # Populate all the known labels with 'to-be-cleared', these should
        # be overwritten with new values later
        for question in self.default_questions:
            contact.extra[question['label']] = u'to-be-cleared'
        # Also fill in junk data for an unknown field which should be left
        # alone.
        contact.extra['litmus'] = u'test'
        yield contact.save()

        yield self.create_survey(self.conversation)
        yield self.app_helper.start_conversation(self.conversation)
        yield self.send_send_survey_command(self.conversation)
        yield self.submit_answers(self.default_questions,
            answers=[
                '2',  # Yellow, skips the second question because of the check
                '2',  # Oranges
                '1',  # Vim
            ])

        # The 4th message should be the closing one
        [closing_message] = yield self.wait_for_messages(1, 4)
        self.assertEqual(closing_message['content'],
            'Thanks for completing the survey')

        user_helper = yield self.app_helper.vumi_helper.get_or_create_user()
        contact_store = user_helper.user_api.contact_store
        contact = yield contact_store.get_contact_by_key(contact.key)
        self.assertEqual(contact.extra['litmus'], u'test')
        self.assertTrue('to-be-cleared' not in contact.extra.values())

    def _reformat_participant_for_comparison(self, participant):
        clone = participant.copy()
        clone['labels'] = json.loads(participant['labels'])
        clone['polls'] = json.loads(participant['polls'])
        clone.pop('updated_at')
        return clone

    def assert_participants_equalish(self, participant1, participant2):
        self.assertEqual(
            self._reformat_participant_for_comparison(participant1),
            self._reformat_participant_for_comparison(participant2))
        self.assertAlmostEqual(
            participant1['updated_at'], participant2['updated_at'], 2)

    @inlineCallbacks
    def complete_survey(self, questions, start_at=0):
        for i in range(len(questions)):
            [msg] = yield self.wait_for_messages(1, i + start_at + 1)
            self.assertEqual(msg['content'], questions[i]['copy'])
            response = str(questions[i]['valid_responses'][0])
            last_sent_msg = yield self.reply_to(msg, response)

        nr_of_messages = 1 + len(questions) + start_at
        all_messages = yield self.app_helper.wait_for_dispatched_outbound(
            nr_of_messages)
        last_msg = all_messages[-1]
        self.assertEqual(last_msg['content'],
            'Thanks for completing the survey')
        self.assertEqual(last_msg['session_event'],
            TransportUserMessage.SESSION_CLOSE)

        poll_id = 'poll-%s' % (self.conversation.key,)

        [app_event] = self.app_helper.get_dispatched_app_events()

        # The poll has been completed and so the results have been
        # archived, get the participant from the archive
        [participant] = (yield self.pm.get_archive(poll_id,
            last_sent_msg['from_addr']))

        self.assertEqual(
            app_event['account_key'], self.conversation.user_account.key)
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

        self.assert_participants_equalish(
            event_participant, participant.dump())

        returnValue(last_msg)

    @inlineCallbacks
    def submit_answers(self, questions, answers, start_at=0):
        for i in range(len(answers)):
            [msg] = yield self.wait_for_messages(1, i + start_at + 1)
            yield self.reply_to(msg, answers.pop(0))

    @inlineCallbacks
    def test_survey_completion(self):
        yield self.app_helper.create_contact(
            u'+27831234567', name=u'First', surname=u'Contact',
            groups=[self.group])
        yield self.create_survey(self.conversation)
        yield self.app_helper.start_conversation(self.conversation)
        yield self.send_send_survey_command(self.conversation)
        yield self.complete_survey(self.default_questions)

    @inlineCallbacks
    def test_ensure_participant_cleared_after_archiving(self):
        contact = yield self.app_helper.create_contact(
            u'+27831234567', name=u'First', surname=u'Contact',
            groups=[self.group])
        yield self.create_survey(self.conversation)
        yield self.app_helper.start_conversation(self.conversation)
        yield self.send_send_survey_command(self.conversation)
        yield self.complete_survey(self.default_questions)
        # This participant should be empty
        poll_id = 'poll-%s' % (self.conversation.key,)
        participant = yield self.pm.get_participant(poll_id, contact.msisdn)
        self.assertEqual(participant.labels, {})

    @inlineCallbacks
    def test_send_message_command(self):
        msg_options = {
            'transport_name': 'sphex_transport',
            'from_addr': '666666',
            'transport_type': 'sphex',
            'helper_metadata': {'foo': {'bar': 'baz'}},
        }
        yield self.app_helper.start_conversation(self.conversation)
        batch_id = self.conversation.batch.key
        yield self.app_helper.dispatch_command(
            "send_message",
            user_account_key=self.conversation.user_account.key,
            conversation_key=self.conversation.key,
            command_data={
                "batch_id": batch_id,
                "to_addr": "123456",
                "content": "hello world",
                "msg_options": msg_options,
            })

        [msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(msg.payload['to_addr'], "123456")
        self.assertEqual(msg.payload['from_addr'], "666666")
        self.assertEqual(msg.payload['content'], "hello world")
        self.assertEqual(msg.payload['transport_name'], "sphex_transport")
        self.assertEqual(msg.payload['transport_type'], "sphex")
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(msg.payload['helper_metadata']['go'], {
            'user_account': self.conversation.user_account.key,
            'conversation_type': 'survey',
            'conversation_key': self.conversation.key,
        })
        self.assertEqual(msg.payload['helper_metadata']['foo'],
                         {'bar': 'baz'})

    @inlineCallbacks
    def test_process_command_send_message_in_reply_to(self):
        yield self.app_helper.start_conversation(self.conversation)
        batch_id = self.conversation.batch.key
        msg = yield self.app_helper.make_stored_inbound(
            self.conversation, "foo")
        command = VumiApiCommand.command(
            'worker', 'send_message',
            user_account_key=self.conversation.user_account.key,
            conversation_key=self.conversation.key,
            command_data={
                u'batch_id': batch_id,
                u'content': u'foo',
                u'to_addr': u'to_addr',
                u'msg_options': {
                    u'transport_name': u'smpp_transport',
                    u'in_reply_to': msg['message_id'],
                    u'transport_type': u'sms',
                    u'from_addr': u'default10080',
                },
            })
        yield self.app.consume_control_command(command)
        [sent_msg] = self.app_helper.get_dispatched_outbound()
        self.assertEqual(sent_msg['to_addr'], msg['from_addr'])
        self.assertEqual(sent_msg['content'], 'foo')
        self.assertEqual(sent_msg['in_reply_to'], msg['message_id'])

    @inlineCallbacks
    def test_closing_menu_if_unavailable(self):
        poll_id = 'poll-%s' % (self.conversation.key,)
        config = yield self.pm.get_config(poll_id)
        self.assertEqual(config, {})  # incomplete or empty

        yield self.app_helper.make_dispatch_inbound(
            "foo", helper_metadata={"poll_id": poll_id},
            conv=self.conversation)
        [reply] = yield self.app_helper.wait_for_dispatched_outbound(1)
        self.assertTrue('Service Unavailable' in reply['content'])
        self.assertEqual(reply['session_event'],
                         TransportUserMessage.SESSION_CLOSE)
