# -*- test-case-name: go.vumitools.tests.test_token_manager -*-
import json
from uuid import uuid4

from twisted.internet.defer import returnValue
from vumi.persist.redis_base import Manager


class TokenManagerException(Exception):
    pass


class InvalidToken(TokenManagerException):
    pass


class MalformedToken(TokenManagerException):
    pass


class TokenManager(object):
    """
    A system for managing 1-time tokens that can expire.
    """
    # How long should tokens live by default in seconds
    DEFAULT_LIFETIME = 60 * 60 * 4

    def __init__(self, redis):
        self.manager = self.redis = redis

    @Manager.calls_manager
    def generate_token(self, user_token_size=6):
        """
        Generate a token that doesn't exist yet but is also short enough
        to not take up too much space in an SMS.

        :param int user_token_size:
            How big the token sent to the user should be. Defaults to 6.
        """
        token_taken = True
        while token_taken:
            full_token = uuid4().hex
            user_token = full_token[0:user_token_size]
            system_token = full_token[user_token_size:]
            token_taken = (yield self.redis.exists(user_token))
        returnValue((user_token, system_token))

    @Manager.calls_manager
    def generate(self, redirect_to, user_id=None, lifetime=None, token=None,
                    extra_params=None):
        """
        Generate a token that redirects to `redirect_to` for exactly
        `lifetime` amount of seconds.

        :param int lifetime:
            How long should the token be valid for in seconds.
        :param int user_id:
            Django user id, if specified this URL is only valid for this user.
        :param tuple token:
            The token to use, if not specified then a unique one will be
            automatically generated. The token is a tuple in the format
            (user_token, system_token). The user token is submitted in the SMS
            the system_token is used internally to ensure that only users
            arriving at the `redirect_to` URL via the token url gain access.
        :param dict extra_params:
            A dictionary that should be stored with the token to store custom
            data in that may be needed when the token is retrieved. Must be
            data that can be encoded as JSON.
        """
        lifetime = lifetime or self.DEFAULT_LIFETIME
        user_token, system_token = token or (yield self.generate_token())
        extra_params = extra_params or {}

        # This is to avoid a possible race condition which could occur in
        # `generate_token()` if two identical user_tokens are generated before
        # either is stored.
        if (yield self.redis.hsetnx(user_token, 'system_token', system_token)):
            yield self.redis.hmset(user_token, {
                'redirect_to': redirect_to,
                'user_id': user_id or '',
                'extra_params': json.dumps(extra_params),
                })
            yield self.redis.expire(user_token, lifetime)
            returnValue(user_token)

        # If we've been given a token then we need to raise an exception as
        # that's not something we can recover from.
        if token:
            raise TokenManagerException('This token has already been issued.')

        # If we end up here then we've hit the race condition and we need to
        # retry.
        value = yield self.generate(redirect_to, user_id=user_id,
                                        lifetime=lifetime, token=token,
                                        extra_params=extra_params)
        returnValue(value)

    @Manager.calls_manager
    def get(self, token, verify=None):
        """
        Retrieve the data for the given token. If there is no match then `None`
        will be returned.

        :param str verify:
            Provide the system_token if matching needs to occur.
        """
        if not (yield self.redis.exists(token)):
            return

        token_data = yield self.redis.hgetall(token)
        if verify is not None and verify != token_data.get('system_token'):
            raise InvalidToken()

        token_data['extra_params'] = json.loads(token_data['extra_params'])
        returnValue(token_data)

    def parse_full_token(self, full_token):
        user_token_length, _, token = full_token.partition('-')
        if not user_token_length.isdigit():
            raise MalformedToken()
        user_token = token[0:int(user_token_length)]
        system_token = token[int(user_token_length):]
        return user_token, system_token

    @Manager.calls_manager
    def verify_get(self, full_token):
        """
        Retrieve the data for a full token as supplied to the `redirect_to`
        URL.

        NOTE: The only reason we're using the @Manager.calls_manager decorator
                here is to ensure that errors are raised consistently.
        """
        user_token, system_token = self.parse_full_token(full_token)
        result = yield self.get(user_token, verify=system_token)
        returnValue(result)

    def delete(self, token):
        """
        Remove a token

        :param str token:
            The token to expire.
        """
        return self.redis.delete(token)
