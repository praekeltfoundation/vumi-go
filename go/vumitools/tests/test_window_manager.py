from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from go.vumitools.window_manager import WindowManager, WindowException
from vumi.persist.txredis_manager import TxRedisManager


class WindowManagerTestCase(TestCase):

    timeout = 1

    @inlineCallbacks
    def setUp(self):
        redis = yield TxRedisManager.from_config({
            'FAKE_REDIS': 'yes please',
        })
        self.window_id = 'window_id'
        self.wm = WindowManager(redis, window_size=10)
        self.wm.create(self.window_id)
        self.redis = self.wm.redis

    @inlineCallbacks
    def test_windows(self):
        windows = yield self.wm.get_windows()
        self.assertTrue(self.window_id in windows)

    def test_window_recreation(self):
        self.assertFailure(self.wm.create(self.window_id), WindowException)

    @inlineCallbacks
    def test_adding_to_window(self):
        for i in range(10):
            yield self.wm.add(self.window_id, i)
        window_key = self.wm.window_key(self.window_id)
        window_members = yield self.redis.zcard(window_key)
        self.assertEqual(window_members, 10)

    @inlineCallbacks
    def test_fetching_from_window(self):
        for i in range(12):
            yield self.wm.add(self.window_id, i)

        flight1 = yield self.wm.next(self.window_id)
        self.assertEqual(len(flight1), 10)
        self.assertEqual((yield self.wm.next(self.window_id)), [])
        self.assertEqual((yield self.wm.count_waiting(self.window_id)), 2)
        self.assertEqual((yield self.wm.count_in_flight(self.window_id)), 10)

        for key in flight1:
            yield self.wm.remove(self.window_id, key)

        self.assertEqual((yield self.wm.count_waiting(self.window_id)), 2)
        self.assertEqual((yield self.wm.count_in_flight(self.window_id)), 0)
        flight2 = yield self.wm.next(self.window_id)
        self.assertEqual(len(flight2), 2)
        self.assertEqual((yield self.wm.next(self.window_id)), None)
        self.assertEqual((yield self.wm.count_waiting(self.window_id)), 0)
        self.assertEqual((yield self.wm.count_in_flight(self.window_id)), 2)

        for key in flight2:
            yield self.wm.remove(self.window_id, key)

        self.assertEqual((yield self.wm.count_in_flight(self.window_id)), 0)
        self.assertEqual((yield self.wm.next(self.window_id)), None)
