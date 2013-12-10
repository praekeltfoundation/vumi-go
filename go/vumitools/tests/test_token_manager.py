from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.vumitools.token_manager import (
    TokenManager, InvalidToken, MalformedToken, TokenManagerException)

from mock import patch


class TestTokenManager(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(PersistenceHelper())
        self.redis = yield self.persistence_helper.get_redis_manager()
        self.tm = TokenManager(self.redis.sub_manager('token_manager'))

    @inlineCallbacks
    def test_token_generation(self):
        token = yield self.tm.generate('/some/path/', lifetime=10)
        token_data = yield self.tm.get(token)
        self.assertEqual(len(token), 6)
        self.assertEqual(token_data['user_id'], '')
        self.assertEqual(token_data['redirect_to'], '/some/path/')
        self.assertTrue(token_data['system_token'])
        self.assertEqual(token_data['extra_params'], {})

    @inlineCallbacks
    def test_token_provided(self):
        token = yield self.tm.generate('/some/path/', lifetime=10,
                                    token=('to', 'ken'))
        self.assertEqual(token, 'to')
        token_data = yield self.tm.get(token)
        self.assertEqual(token_data['system_token'], 'ken')

    @inlineCallbacks
    def test_unknown_token(self):
        self.assertEqual((yield self.tm.get('foo')), None)

    def test_malformed_token(self):
        return self.assertFailure(
            self.tm.verify_get('A-token-starting-with-a-digit'),
            MalformedToken)

    @inlineCallbacks
    def test_token_verify(self):
        token = yield self.tm.generate('/foo/', token=('to', 'ken'))
        yield self.assertFailure(self.tm.get(token, verify='bar'),
            InvalidToken)
        self.assertEqual((yield self.tm.get(token, verify='ken')), {
            'user_id': '',
            'system_token': 'ken',
            'redirect_to': '/foo/',
            'extra_params': {},
            })

    @inlineCallbacks
    def test_token_delete(self):
        token = yield self.tm.generate('/foo/')
        self.assertTrue((yield self.tm.get(token)))
        self.assertTrue((yield self.tm.delete(token)))
        self.assertFalse((yield self.tm.get(token)))

    @inlineCallbacks
    def test_token_extra_params(self):
        extra_params = {'one': 'two', 'three': 4}
        token = yield self.tm.generate('/foo/', extra_params=extra_params)
        token_data = yield self.tm.get(token)
        self.assertEqual(token_data['extra_params'], extra_params)

    @inlineCallbacks
    def test_reuse_existing_token(self):
        token = ('to', 'ken')
        yield self.tm.generate('/foo/', token=token)
        yield self.assertFailure(self.tm.generate('/foo/', token=token),
            TokenManagerException)

    def test_parse_full_token(self):
        user_token, sys_token = self.tm.parse_full_token('1-ab')
        self.assertEqual(user_token, 'a')
        self.assertEqual(sys_token, 'b')
        self.assertRaises(MalformedToken, self.tm.parse_full_token, 'a-bc')

    @inlineCallbacks
    def test_race_condition(self):
        # claim these
        yield self.tm.generate('/foo/', token=('to1', 'ken'))
        yield self.tm.generate('/foo/', token=('to2', 'ken'))
        # patch the generate command to first return the ones that already
        # exist it should, continue trying until an un-used token is found
        with patch.object(TokenManager, 'generate_token') as mock:
            mock.side_effect = [('to1', 'ken'), ('to2', 'ken'), ('to3', 'ken')]
            user_token = yield self.tm.generate('/foo/')
        self.assertEqual(user_token, 'to3')
