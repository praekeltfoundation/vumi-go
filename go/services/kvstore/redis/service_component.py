import json

from vumi import log
from vumi.persist.model import Manager
from twisted.internet.defer import returnValue


class RedisKVStoreServiceComponent(object):
    """
    A service component that provides access to a simple key-value store in
    Redis.

    TODO: Allow this to use a separate Redis instance instead of the one from
          VumiApi.
    TODO: Something about key expiry.
    """
    def __init__(self, service_def):
        self.service_def = service_def
        self.config = service_def.get_config()
        self.vumi_api = service_def.vumi_api
        self.user_account_key = service_def.service.user_account.key
        self.redis = self.vumi_api.redis.sub_manager(self.config.key_prefix)
        # Hackity hack: Replace _key_prefix on our submanager to avoid problems
        # with separators.
        self.redis._key_prefix = self.config.key_prefix
        self.keys_per_user_hard = self.config.keys_per_user
        self.keys_per_user_soft = int(0.8 * self.keys_per_user_hard)

    def _count_key(self):
        return "#".join(["count", self.user_account_key])

    def _sandboxed_key(self, key):
        return "#".join(["sandboxes", self.user_account_key, key])

    def _too_many_keys(self, command):
        return self.reply(command, success=False,
                          reason="Too many keys")

    @Manager.calls_manager('redis')
    def check_keys(self, key):
        if (yield self.redis.exists(key)):
            returnValue(True)
        count_key = self._count_key()
        key_count = yield self.redis.incr(count_key, 1)
        if key_count >= self.keys_per_user_soft:
            if key_count <= self.keys_per_user_hard:
                log.warning(
                    'Redis soft limit of %s keys reached for account %s. '
                    'Once the hard limit of %s is reached no more keys '
                    'can be written.' % (
                        self.keys_per_user_soft,
                        self.user_account_key,
                        self.keys_per_user_hard))
            else:
                log.warning(
                    'Redis hard limit of %s keys reached for account %s. '
                    'No more keys can be written.' % (
                        self.keys_per_user_hard, self.user_account_key))
                yield self.redis.incr(count_key, -1)
                returnValue(False)
        returnValue(True)

    @Manager.calls_manager('redis')
    def set_value(self, key, value):
        """
        Set the value of a key.

        :param str key: The key whose value should be set.
        :param value: The value to store. May be any JSON serializable object.
        """
        key = self._sandboxed_key(key)
        if not (yield self.check_keys(key)):
            raise RuntimeError("Too many keys")  # TODO: Better exception.
        yield self.redis.set(key, json.dumps(value))

    @Manager.calls_manager('redis')
    def get_value(self, key, default=None):
        """
        Retrieve the value of a key.

        :param str key: The key whose value should be retrieved.
        :param default: The default value to return if no value is found.
        """
        key = self._sandboxed_key(key)
        raw_value = yield self.redis.get(key)
        value = json.loads(raw_value) if raw_value is not None else default
        returnValue(value)

    @Manager.calls_manager('redis')
    def delete_value(self, key):
        """
        Delete a key.

        :param str key: The key to delete.

        :returns:
            ``True`` if the key existed before deletion, ``False`` otherwise.
        """
        key = self._sandboxed_key(key)
        existed = bool((yield self.redis.delete(key)))
        if existed:
            yield self.redis.incr(self._count_key(), -1)
        returnValue(existed)
