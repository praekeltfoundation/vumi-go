# -*- test-case-name: go.vumitools.tests.test_utils -*-

from vumi.middleware.tagger import TaggingMiddleware
from go.vumitools.middleware import OptOutMiddleware


class MessageMetadataHelper(object):
    """Look up various bits of metadata for a Vumi Go message.

    Any Go inbound message that has reached the main dispatcher, will already
    have at least `user_account_key` in helper metadata. `conversation_type`
    and `conversation_key` are set once the message gets routed to the
    conversation.

    TODO: Something about non-conversation routing blocks.

    We store metadata in two places:

    1. Keys into the various stores go into the message helper_metadata.
       This is helpful for preventing unnecessary duplicate lookups between
       workers.

    2. Objects retreived from those stores get stashed on the message object.
       This is helpful for preventing duplicate lookups within a worker.
       (Between different middlewares, for example.)
    """

    def __init__(self, vumi_api, message):
        self.vumi_api = vumi_api
        self.message = message

        # Easier access to metadata.
        message_metadata = message.get('helper_metadata', {})
        self._go_metadata = message_metadata.setdefault('go', {})

        # A place to store objects we don't want serialised.
        if not hasattr(message, '_store_objects'):
            message._store_objects = {}
        self._store_objects = message._store_objects

        # If we don't have a tag, we want to blow up early in some places.
        self.tag = TaggingMiddleware.map_msg_to_tag(message)

    def is_sensitive(self):
        """
        Returns True if the contents of the message have been marked as
        being sensitive. This could mean the SMS contains information such as
        unique codes, airtime pins or other values that should not be displayed
        in a UI
        """
        return bool(self._go_metadata.get('sensitive'))

    def has_user_account(self):
        return 'user_account' in self._go_metadata

    def get_account_key(self):
        # TODO: Better exception.
        return self._go_metadata['user_account']

    def get_user_api(self):
        return self.vumi_api.get_user_api(self.get_account_key())

    def get_conversation_key(self):
        # TODO: Better exception.
        return self._go_metadata['conversation_key']

    def get_conversation(self):
        return self.get_user_api().get_wrapped_conversation(
            self.get_conversation_key())

    def get_conversation_info(self):
        conversation_info = {}

        for field in ['user_account', 'conversation_type', 'conversation_key']:
            if field in self._go_metadata:
                conversation_info[field] = self._go_metadata[field]

        if len(conversation_info) != 3:
            return None
        return conversation_info

    def set_conversation_info(self, conversation_type, conversation_key):
        self._go_metadata.update({
            'conversation_type': conversation_type,
            'conversation_key': conversation_key,
        })

    def set_user_account(self, user_account):
        self._go_metadata.update({
            'user_account': user_account,
        })

    def is_optout_message(self):
        return OptOutMiddleware.is_optout_message(self.message)

    def get_router_key(self):
        # TODO: Better exception.
        return self._go_metadata['router_key']

    def get_router(self):
        return self.get_user_api().get_router(
            self.get_router_key())

    def get_router_info(self):
        router_info = {}

        for field in ['user_account', 'router_type', 'router_key']:
            if field in self._go_metadata:
                router_info[field] = self._go_metadata[field]

        if len(router_info) != 3:
            return None
        return router_info

    def set_router_info(self, router_type, router_key):
        self._go_metadata.update({
            'router_type': router_type,
            'router_key': router_key,
        })

    def set_tag(self, tag):
        TaggingMiddleware.add_tag_to_msg(self.message, tag)
        self.tag = TaggingMiddleware.map_msg_to_tag(self.message)
