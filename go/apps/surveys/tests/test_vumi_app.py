# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

import uuid
import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage

from go.apps.surveys.vumi_app import SurveyApplication
from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApiCommand


class TestSurveyApplication(AppWorkerTestCase):

    application_class = SurveyApplication
    transport_type = u'sms'

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
        super(TestSurveyApplication, self).setUp()

        # Setup the SurveyApplication
        self.app = yield self.get_application({
                'vxpolls': {'prefix': 'test.'},
                })

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)

        # Add tags
        yield self.setup_tagpools()

        # Setup the poll manager
        self.pm = self.app.pm

        # Give a user access to a tagpool
        self.user_api.api.account_store.tag_permissions(uuid.uuid4().hex,
            tagpool=u"pool", max_keys=None)

        # Create a group and a conversation
        self.group = yield self.create_group(u'test group')

        # Make the contact store searchable
        yield self.user_api.contact_store.contacts.enable_search()

        self.conversation = yield self.create_conversation()
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

    def get_contact(self, contact_key):
        return self.user_api.contact_store.get_contact_by_key(contact_key)

    @inlineCallbacks
    def reply_to(self, msg, content, continue_session=True, **kw):
        reply = TransportUserMessage(
            to_addr=msg['from_addr'],
            from_addr=msg['to_addr'],
            group=msg['group'],
            content=content,
            transport_name=msg['transport_name'],
            transport_type=msg['transport_type'],
            **kw)
        yield self.dispatch_to_conv(reply, self.conversation)
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
    def send_send_survey_command(self, conversation):
        batch_id = yield self.conversation.get_latest_batch_key()
        yield self.dispatch_command(
            "send_survey",
            user_account_key=self.user_account.key,
            conversation_key=conversation.key,
            batch_id=batch_id,
            msg_options={},
            is_client_initiated=False,
            delivery_class=conversation.delivery_class,
        )

    @inlineCallbacks
    def test_clearing_old_survey_data(self):
        contact = yield self.create_contact(u'First', u'Contact',
            msisdn=u'+27831234567', groups=[self.group])
        # Populate all the known labels with 'to-be-cleared', these should
        # be overwritten with new values later
        for question in self.default_questions:
            contact.extra[question['label']] = u'to-be-cleared'
        # Also fill in junk data for an unknown field which should be left
        # alone.
        contact.extra['litmus'] = u'test'
        yield contact.save()

        self.create_survey(self.conversation)
        yield self.start_conversation(self.conversation)
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

        contact = yield self.get_contact(contact.key)
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
        yield self.create_contact(u'First', u'Contact',
            msisdn=u'+27831234567', groups=[self.group])
        self.create_survey(self.conversation)
        yield self.start_conversation(self.conversation)
        yield self.send_send_survey_command(self.conversation)
        yield self.complete_survey(self.default_questions)

    @inlineCallbacks
    def test_ensure_participant_cleared_after_archiving(self):
        contact = yield self.create_contact(u'First', u'Contact',
            msisdn=u'+27831234567', groups=[self.group])
        self.create_survey(self.conversation)
        yield self.start_conversation(self.conversation)
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
        yield self.start_conversation(self.conversation)
        batch_id = yield self.conversation.get_latest_batch_key()
        yield self.dispatch_command(
            "send_message",
            user_account_key=self.user_account.key,
            conversation_key=self.conversation.key,
            command_data={
            "batch_id": batch_id,
            "to_addr": "123456",
            "content": "hello world",
            "msg_options": msg_options,
        })

        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg.payload['to_addr'], "123456")
        self.assertEqual(msg.payload['from_addr'], "666666")
        self.assertEqual(msg.payload['content'], "hello world")
        self.assertEqual(msg.payload['transport_name'], "sphex_transport")
        self.assertEqual(msg.payload['transport_type'], "sphex")
        self.assertEqual(msg.payload['message_type'], "user_message")
        self.assertEqual(msg.payload['helper_metadata']['go'], {
            'user_account': self.user_account.key,
            'conversation_type': 'survey',
            'conversation_key': self.conversation.key,
        })
        self.assertEqual(msg.payload['helper_metadata']['foo'],
                         {'bar': 'baz'})

    @inlineCallbacks
    def test_process_command_send_message_in_reply_to(self):
        yield self.start_conversation(self.conversation)
        batch_id = yield self.conversation.get_latest_batch_key()
        msg = self.mkmsg_in(message_id=uuid.uuid4().hex)
        yield self.store_inbound_msg(msg)
        command = VumiApiCommand.command(
            'worker', 'send_message',
            user_account_key=self.user_account.key,
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
        [sent_msg] = self.get_dispatched_messages()
        self.assertEqual(sent_msg['to_addr'], msg['from_addr'])
        self.assertEqual(sent_msg['content'], 'foo')
        self.assertEqual(sent_msg['in_reply_to'], msg['message_id'])

    @inlineCallbacks
    def test_closing_menu_if_unavailable(self):
        poll_id = 'poll-%s' % (self.conversation.key,)
        config = yield self.pm.get_config(poll_id)
        self.assertEqual(config, {})  # incomplete or empty

        msg = self.mkmsg_in()
        msg['helper_metadata']['poll_id'] = poll_id
        yield self.dispatch_to_conv(msg, self.conversation)
        [reply] = yield self.wait_for_dispatched_messages(1)
        self.assertTrue('Service Unavailable' in reply['content'])
        self.assertEqual(reply['session_event'],
                         TransportUserMessage.SESSION_CLOSE)
