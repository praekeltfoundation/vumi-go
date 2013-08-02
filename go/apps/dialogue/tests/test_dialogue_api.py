"""Tests for go.apps.dialogue.dialogue_api."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from go.apps.dialogue.dialogue_api import DialogueActionDispatcher
from go.vumitools.api import VumiApi
from go.vumitools.tests.utils import GoAppWorkerTestMixin


class DialogueActionDispatcherTestCase(TestCase, GoAppWorkerTestMixin):

    use_riak = True

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        self.config = self.mk_config({})
        self.vumi_api = yield VumiApi.from_config_async(self.config)
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)
        self.dispatcher = DialogueActionDispatcher(
            self.account.key, self.vumi_api)

    def create_dialogue(self, poll):
        config = {
            "poll": poll,
        }
        return self.create_conversation(
            conversation_type=u'dialogue', config=config)

    @inlineCallbacks
    def test_get_poll(self):
        conv = yield self.create_dialogue(poll={"foo": "bar"})
        result = yield self.dispatcher.action_get_poll(
            self.user_api, conv)
        self.assertEqual(result, {"poll": {"foo": "bar"}})

    @inlineCallbacks
    def test_save_poll(self):
        conv = yield self.create_dialogue(poll={})
        result = yield self.dispatcher.action_save_poll(
            self.user_api, conv, poll={"foo": "bar"})
        self.assertEqual(result, {"saved": True})
        conv = yield self.user_api.get_conversation(conv.key)
        self.assertEqual(conv.config, {
            "poll": {"foo": "bar"},
        })
