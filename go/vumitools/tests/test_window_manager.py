from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import Clock

from go.vumitools.window_manager import WindowManager, WindowException
from vumi.tests.utils import PersistenceMixin


class WindowManagerTestCase(TestCase, PersistenceMixin):

    timeout = 1

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        redis = yield self.get_redis_manager()
        self.window_id = 'window_id'
        self.wm = WindowManager(redis, window_size=10,
            max_flight_retries=3)
        yield self.wm.create(self.window_id)
        self.wm.gc.clock = self.clock = Clock()
        self.redis = self.wm.redis

    @inlineCallbacks
    def tearDown(self):
        yield self._persist_tearDown()
        self.wm.stop()

    @inlineCallbacks
    def test_windows(self):
        windows = yield self.wm.get_windows()
        self.assertTrue(self.window_id in windows)

    def test_window_recreation(self):
        return self.assertFailure(self.wm.create(self.window_id),
            WindowException)

    @inlineCallbacks
    def test_window_removal(self):
        yield self.wm.add(self.window_id, 1)
        yield self.assertFailure(self.wm.remove_window(self.window_id),
            WindowException)
        key = yield self.wm.next(self.window_id)
        item = yield self.wm.get(self.window_id, key)
        self.assertEqual(item, 1)
        self.assertEqual((yield self.wm.remove_window(self.window_id)), None)

    @inlineCallbacks
    def test_adding_to_window(self):
        for i in range(10):
            yield self.wm.add(self.window_id, i)
        window_key = self.wm.window_key(self.window_id)
        window_members = yield self.redis.llen(window_key)
        self.assertEqual(window_members, 10)

    @inlineCallbacks
    def test_fetching_from_window(self):
        for i in range(12):
            yield self.wm.add(self.window_id, i)

        flight_keys = []
        for i in range(10):
            flight_key = yield self.wm.next(self.window_id)
            self.assertTrue(flight_key)
            flight_keys.append(flight_key)

        out_of_window_flight = yield self.wm.next(self.window_id)
        self.assertEqual(out_of_window_flight, None)

        # We should get data out in the order we put it in
        for i, flight_key in enumerate(flight_keys):
            data = yield self.wm.get(self.window_id, flight_key)
            self.assertEqual(data, i)

        # Removing one should allow for space for the next to fill up
        yield self.wm.remove(self.window_id, flight_keys[0])
        next_flight_key = yield self.wm.next(self.window_id)
        self.assertTrue(next_flight_key)

    @inlineCallbacks
    def assert_count_waiting(self, window_id, amount):
        self.assertEqual((yield self.wm.count_waiting(window_id)), amount)

    @inlineCallbacks
    def assert_expired_keys(self, window_id, amount, expected_tries=1):
        # Stuff has taken too long and so we should get 10 expired keys
        expired_keys = yield self.wm.get_expired_flight_keys(window_id)
        self.assertEqual(len(expired_keys), amount)
        for key in expired_keys:
            tries = yield self.wm.get_tries(window_id, key)
            self.assertEqual(int(tries), expected_tries)

    @inlineCallbacks
    def assert_in_flight(self, window_id, amount):
        self.assertEqual((yield self.wm.count_in_flight(window_id)),
            amount)

    @inlineCallbacks
    def slide_window(self, limit=10):
        for i in range(limit):
            yield self.wm.next(self.window_id)

    @inlineCallbacks
    def test_retries(self):

        for i in range(10):
            yield self.wm.add(self.window_id, i)

        for i in range(3):  # max nr of retries + 1
            yield self.slide_window()
            self.clock.advance(10)
            yield self.wm.clear_or_retry_flight_keys()

        self.assert_in_flight(self.window_id, 0)
        self.assert_count_waiting(self.window_id, 0)
        self.assert_expired_keys(self.window_id, 0, None)
