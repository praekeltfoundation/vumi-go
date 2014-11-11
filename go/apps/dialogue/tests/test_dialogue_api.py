"""Tests for go.apps.dialogue.dialogue_api."""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.dialogue.dialogue_api import DialogueActionDispatcher
from go.apps.dialogue.tests.dummy_polls import simple_poll
from go.vumitools.tests.helpers import VumiApiHelper


class TestDialogueActionDispatcher(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())

        self.user_helper = yield self.vumi_helper.make_user(u'user')
        self.dispatcher = DialogueActionDispatcher(
            self.user_helper.account_key, self.vumi_helper.get_vumi_api())

    def create_dialogue(self, poll):
        return self.user_helper.create_conversation(
            conversation_type=u'dialogue', config={"poll": poll})

    @inlineCallbacks
    def test_get_poll(self):
        conv = yield self.create_dialogue(poll={"foo": "bar"})
        result = yield self.dispatcher.action_get_poll(
            self.user_helper.user_api, conv)
        self.assertEqual(result, {"poll": {"foo": "bar"}})

    @inlineCallbacks
    def test_save_poll(self):
        conv = yield self.create_dialogue(poll={})
        result = yield self.dispatcher.action_save_poll(
            self.user_helper.user_api, conv, poll={"foo": "bar"})
        self.assertEqual(result, {"saved": True})
        conv = yield self.user_helper.get_conversation(conv.key)
        self.assertEqual(conv.config, {"poll": {"foo": "bar"}})

    @inlineCallbacks
    def test_save_poll_endpoints(self):
        poll = simple_poll()

        poll['channel_types'] = [{
            'name': u'sms',
            'label': u'SMS'
        }, {
            'name': u'twitter',
            'label': u'Twitter'
        }]

        poll['states'] = [{
            'type': 'foo'
        }, {
            'type': 'send',
            'channel_type': 'sms'
        }, {
            'type': 'foo'
        }, {
            'type': 'send',
            'channel_type': 'twitter'
        }, {
            'type': 'send',
            'channel_type': 'sms'
        }]

        conv = yield self.create_dialogue(poll={})
        yield self.dispatcher.action_save_poll(
            self.user_helper.user_api, conv, poll=poll)

        conv = yield self.user_helper.get_conversation(conv.key)
        self.assertEqual(list(conv.extra_endpoints), ['SMS', 'Twitter'])
