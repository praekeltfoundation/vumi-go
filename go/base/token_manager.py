from uuid import uuid4


class TokenManager(object):
    """
    A system for managing 1-time tokens that can expire.
    """
    # How long should tokens live by default in seconds
    DEFAULT_LIFETIME = 60 * 60 * 4

    def __init__(self, redis):
        self.redis = redis

    def generate_token(self, length=6):
        """
        Generate a token that doesn't exist yet but is also short enough
        to not take up too much space in an SMS.
        """
        token_taken = True
        while token_taken:
            token = uuid4().hex[0:length]
            token_taken = self.redis.exists(token)
        return token

    def generate(self, redirect_to, user_id=None, lifetime=None, token=None):
        """
        Generate a token that redirects to `redirect_to` for exactly
        `lifetime` amount of seconds.

        :param int lifetime:
            How long should the token be valid for in seconds.
        :param int user_id:
            Django user id, if specified this URL is only valid for this user.
        :param str token:
            The token to use, if not specified then a unique one will be
            automatically generated.
        """
        lifetime = lifetime or self.DEFAULT_LIFETIME
        token = token or self.generate_token()
        self.redis.hmset(token, {
            'redirect_to': redirect_to,
            'user_id': user_id or '',
            })
        self.redis.expire(token, lifetime)
        return token

    def get(self, token):
        """
        Retrieve the data for the given token, it it doesn't exist it'll
        return an empty dictionary.
        """
        return self.redis.hgetall(token)
