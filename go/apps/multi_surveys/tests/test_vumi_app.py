# -*- coding: utf-8 -*-

"""Tests for go.apps.multi_surveys.vumi_app"""

import uuid

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.tests.utils import LogCatcher

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.multi_surveys.vumi_app import MultiSurveyApplication
from go.vumitools.opt_out import OptOutStore


class TestMultiSurveyApplication(AppWorkerTestCase):

    application_class = MultiSurveyApplication
    transport_type = u'sms'

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
        0: (u'You have completed the registration questions.'),
        1: (u"You've done this week's 2 quiz questions. "
            "Please dial *120*2112# again next week "
            "for new questions. Stay well! Visit askmama.mobi"),
        }

    @inlineCallbacks
    def setUp(self):
        super(TestMultiSurveyApplication, self).setUp()

        # Setup the SurveyApplication
        self.app = yield self.get_application({
                'vxpolls': {'prefix': 'test.'},
                'is_demo': False,
                })

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!
        self._persist_riak_managers.append(self.vumi_api.manager)

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)

        # Add tags
        yield self.declare_tags(self.vumi_api,
                                [("pool", "tag1"), ("pool", "tag2")])
        yield self.set_pool_metadata(self.vumi_api, "pool", {
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

        self.conversation = yield self.create_conversation(
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
    def create_survey(self, conversation, polls=None, end_response=None):
        # Create a sample survey
        polls = polls or self.default_polls
        poll_id_prefix = 'poll-%s' % (conversation.key,)
        for poll_number, questions in polls.iteritems():
            poll_id = "%s_%d" % (poll_id_prefix, poll_number)
            config = yield self.pm.get_config(poll_id)
            config.update({
                'poll_id': poll_id,
                'transport_name': self.transport_name,
                'questions': questions,
                })
            config.setdefault('survey_completed_response',
                              (end_response or
                               'Thanks for completing the survey'))
            self.pm.set(poll_id, config)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.wait_for_dispatched_messages(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def tearDown(self):
        self.pm.stop()
        yield super(TestMultiSurveyApplication, self).tearDown()

    @inlineCallbacks
    def test_start(self):
        self.contact1 = yield self.create_contact(name=u'First',
            surname=u'Contact', msisdn=u'27831234567', groups=[self.group])
        self.contact2 = yield self.create_contact(name=u'Second',
            surname=u'Contact', msisdn=u'27831234568', groups=[self.group])
        yield self.create_survey(self.conversation)
        with LogCatcher() as log:
            yield self.start_conversation(self.conversation)
            self.assertEqual(log.errors, [])

        [msg1, msg2] = yield self.wait_for_dispatched_messages(2)
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
    def complete_empty_survey(self, polls, start_at=0):
        questions = [{
                'copy': self.end_of_survey_copy[1],
                'valid_responses': [u''],
                'session_event': 'close',
                }]
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
        yield self.create_survey(self.conversation)
        yield self.start_conversation(self.conversation)
        yield self.complete_survey(self.default_polls)

    @inlineCallbacks
    def test_surveys_in_succession(self):
        yield self.create_contact(u'First', u'Contact',
            msisdn=u'27831234567', groups=[self.group])
        yield self.create_survey(self.conversation)
        yield self.start_conversation(self.conversation)
        start_at = 0
        for i in range(1):
            msgs = yield self.complete_survey(self.default_polls,
                                              start_at=start_at)
            start_at += len(msgs)
            # any input will restart the survey
            yield self.reply_to(msgs[-1], 'hi')

        for i in range(2):
            msgs = yield self.complete_empty_survey(self.default_polls,
                                              start_at=start_at)
            start_at += len(msgs)
            # any input will restart the survey
            yield self.reply_to(msgs[-1], 'hi')

    @inlineCallbacks
    def test_surveys_in_succession_demo_mode(self):
        self.app.is_demo = True
        yield self.create_contact(u'First', u'Contact',
            msisdn=u'27831234567', groups=[self.group])
        yield self.create_survey(self.conversation)
        yield self.start_conversation(self.conversation)
        start_at = 0
        for i in range(3):
            msgs = yield self.complete_survey(self.default_polls,
                                              start_at=start_at)
            start_at += len(msgs)
            # any input will restart the survey
            yield self.reply_to(msgs[-1], 'hi')

    @inlineCallbacks
    def test_survey_for_opted_out_user(self):

        self.contact1 = yield self.create_contact(name=u'First',
            surname=u'Contact', msisdn=u'27831234561', groups=[self.group])
        yield self.create_survey(self.conversation)
        with LogCatcher() as log:
            yield self.start_conversation(self.conversation)
            self.assertEqual(log.errors, [])

        # First run through to the second poll
        [msg1] = yield self.wait_for_dispatched_messages(1)
        self.clear_dispatched_messages()
        self.assertEqual(msg1['content'], self.default_polls[0][0]['copy'])
        yield self.reply_to(msg1, "1")
        [msg2] = yield self.wait_for_dispatched_messages(1)
        self.clear_dispatched_messages()
        self.assertEqual(msg2['content'], self.end_of_survey_copy[0])
        yield self.reply_to(msg2, "1")
        [msg3] = yield self.wait_for_dispatched_messages(1)
        self.clear_dispatched_messages()
        self.assertEqual(msg3['content'], self.default_polls[1][0]['copy'])

        # Now opt the msisdn out
        opt_out_addr = '27831234561'
        opt_out_store = OptOutStore(self.app.manager, self.user_account.key)
        yield opt_out_store.new_opt_out('msisdn', opt_out_addr,
                                        {'message_id': u'test_message_id'})

        # Check that on re-entry the survey is reset and the
        # opening copy is delivered
        yield self.reply_to(msg3, "1")
        [msg4] = yield self.wait_for_dispatched_messages(1)
        self.clear_dispatched_messages()
        self.assertEqual(msg4['content'], self.default_polls[0][0]['copy'])

        opt_out = yield opt_out_store.get_opt_out('msisdn', opt_out_addr)
        self.assertEqual(opt_out, None)
