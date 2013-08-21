# -*- test-case-name: go.apps.jsbox.tests.test_kv -*-
# -*- coding: utf-8 -*-

import json

from twisted.internet.defer import returnValue

from vumi.persist.redis_base import Manager


class KeyValueManager(object):
    """
    Retrieves key value data for a jsbox application.
    """

    # this uses Manager.calls_manager so that it can be used from
    # Django.

    def __init__(self, redis):
        self.redis = self.manager = redis

    def _sandboxed_key(self, sandbox_id, key):
        # TODO: refactor vumi.application.sandbox.RedisResource
        #       to make this a static method (or something else
        #       that allows sharing this logic).
        return "#".join(["sandboxes", sandbox_id, key])

    def _sub_manager_for_user_store(self, campaign_key, user_store):
        if user_store:
            user_key_prefix = "users.%s" % (user_store,)
        else:
            user_key_prefix = "users"
        sub_store_key = self._sandboxed_key(campaign_key, user_key_prefix)
        sub_redis = self.redis.sub_manager(sub_store_key)
        # TODO: make key_separator an option on sub_manager
        sub_redis._key_separator = "."
        return sub_redis

    @Manager.calls_manager
    def answers(self, campaign_key, user_store=None):
        sub_redis = self._sub_manager_for_user_store(campaign_key, user_store)
        keys = yield sub_redis.keys()
        items = {}
        for key in keys:
            raw_value = yield sub_redis.get(key)
            try:
                value = json.loads(raw_value)
            except:
                continue
            items[key] = value
        returnValue(items)
