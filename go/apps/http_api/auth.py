from zope.interface import implements

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import resource
from twisted.cred import portal, checkers, credentials, error


class ConversationRealm(object):
    implements(portal.IRealm)

    def __init__(self, resource):
        self.resource = resource

    def requestAvatar(self, user, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, self.resource, lambda: None)
        raise NotImplementedError()


class ConversationAccessChecker(object):
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)

    def __init__(self, vumi_api, conversation_key):
        self.vumi_api = vumi_api
        self.conversation_key = conversation_key

    @inlineCallbacks
    def requestAvatarId(self, credentials):
        username = credentials.username
        token = credentials.password
        user_exists = yield self.vumi_api.user_exists(username)
        if user_exists:
            user_api = self.vumi_api.get_user_api(username)
            conversation = yield user_api.get_wrapped_conversation(
                                                        self.conversation_key)
            if conversation is not None:
                metadata = conversation.get_metadata(default={})
                http_api_metadata = metadata.get('http_api', {})
                tokens = http_api_metadata.get('api_tokens', [])
                if token in tokens:
                    returnValue(username)
        raise error.UnauthorizedLogin()
