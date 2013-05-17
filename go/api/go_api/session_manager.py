# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_session_manager -*-

"""Session manager to provide access to Django sessions from both
   Django and Twisted workers (e.g. the Go API).
   """

from twisted.internet.defer import returnValue

from vumi.persist.redis_base import Manager

GO_USER_ACCOUNT_KEY = '_go_user_account_key'


class SessionManager(object):
    """A manager for sessions.

    :type redis: TxRedisManager or RedisManager
    :param redis:
        Redis manager object.
    """

    def __init__(self, redis):
        self.manager = redis

    def _session_key(self, session_key):
        return "sessions.%s" % (session_key,)

    def exists(self, session_key):
        """Returns True if the session_key exists, False otherwise."""
        return self.manager.exists(self._session_key(session_key))

    def get_session(self, session_key):
        """Returns the session_data for the session_key or None if the
           session_key doesn't exist or has expired.
           """
        return self.manager.get(self._session_key(session_key))

    @Manager.calls_manager
    def create_session(self, session_key, session_data, expire_seconds):
        """Attempts to create the given session entry. Returns False
           if the attempt to create the session fails and True otherwise.
           """
        created = yield self.manager.setnx(
            self._session_key(session_key), session_data)
        if created:
            yield self.manager.expire(expire_seconds)
        returnValue(created)

    @Manager.calls_manager
    def save_session(self, session_key, session_data, expire_seconds):
        """Save the given session entry."""
        yield self.manager.set(self._session_key(session_key), session_data)
        yield self.manager.expire(expire_seconds)

    def delete_session(self, session_key):
        """Deletes the given session entry."""
        return self.manager.delete(self._session_key(session_key))
