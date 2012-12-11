from uuid import uuid4


class TokenManager(object):
    """
    A system for managing 1-time tokens that can expire.
    """
    # How long should tokens live by default in seconds
    DEFAULT_LIFETIME = 60 * 60 * 4

    def __init__(self, redis):
        self.redis = redis

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
            token_taken = self.redis.exists(user_token)
        return (user_token, system_token)

    def generate(self, redirect_to, user_id=None, lifetime=None, token=None):
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
        """
        lifetime = lifetime or self.DEFAULT_LIFETIME
        user_token, system_token = token or self.generate_token()
        self.redis.hmset(user_token, {
            'redirect_to': redirect_to,
            'user_id': user_id or '',
            'system_token': system_token,
            })
        self.redis.expire(user_token, lifetime)
        return user_token

    def get(self, token, verify=None):
        """
        Retrieve the data for the given token, it it doesn't exist it'll
        return an empty dictionary.

        :param str verify:
            Provide the system_token if matching needs to occur. If there
            is no match then an empty dictionary will be returned.
        """
        token_data = self.redis.hgetall(token)
        if verify is not None and verify != token_data['system_token']:
            return {}
        return token_data

    def verify_get(self, full_token):
        """
        Retrieve the data for a full token as supplied to the `redirect_to`
        URL.
        """
        user_token_length, _, token = full_token.partition('-')
        user_token = token[0:int(user_token_length)]
        system_token = token[int(user_token_length):]
        return self.get(user_token, verify=system_token)

    def delete(self, token):
        """
        Remove a token

        :param str token:
            The token to expire.
        """
        return self.redis.delete(token)
