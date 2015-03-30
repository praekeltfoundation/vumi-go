# -*- test-case-name: go.vumitools.tests.test_utils -*-

from twisted.internet.defer import succeed

from vumi.middleware.tagger import TaggingMiddleware


class MessageMetadataDictHelper(object):
    """Manage various bits of metadata for a Vumi Go message.

    This version of the helper operates only on the `helper_metadata` dict and
    thus has no access to a `VumiApi` object.
    """

    def __init__(self, helper_metadata):
        self._go_metadata = helper_metadata.setdefault('go', {})

    def is_sensitive(self):
        """
        Returns True if the contents of the message have been marked as
        being sensitive. This could mean the SMS contains information such as
        unique codes, airtime pins or other values that should not be displayed
        in a UI
        """
        return bool(self._go_metadata.get('sensitive'))

    def set_sensitive(self, value):
        self._go_metadata['sensitive'] = value

    def has_user_account(self):
        return 'user_account' in self._go_metadata

    def get_account_key(self):
        # TODO: Better exception.
        return self._go_metadata['user_account']

    def is_paid(self):
        """Return ``True`` if the message has been processed by the
        ``BillingWorker``, ``False`` otherwise

        """
        return self._go_metadata.get('is_paid', False)

    def get_conversation_info(self):
        conversation_info = {}

        for field in ['user_account', 'conversation_type', 'conversation_key']:
            if field in self._go_metadata:
                conversation_info[field] = self._go_metadata[field]

        if len(conversation_info) != 3:
            return None
        return conversation_info

    def get_conversation_key(self):
        # TODO: Better exception.
        return self._go_metadata['conversation_key']

    def set_conversation_info(self, conversation_type, conversation_key):
        self._go_metadata.update({
            'conversation_type': conversation_type,
            'conversation_key': conversation_key,
        })

    def set_user_account(self, user_account):
        self._go_metadata.update({
            'user_account': user_account,
        })

    def set_paid(self):
        self._go_metadata.update({'is_paid': True})

    def reset_paid(self):
        self._go_metadata.pop('is_paid', None)

    def get_router_key(self):
        # TODO: Better exception.
        return self._go_metadata['router_key']

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

    def add_conversation_metadata(self, conversation):
        self.set_user_account(conversation.user_account.key)
        self.set_conversation_info(
            conversation.conversation_type, conversation.key)

    def add_router_metadata(self, router):
        self.set_user_account(router.user_account.key)
        self.set_router_info(router.router_type, router.key)


class MessageMetadataHelper(MessageMetadataDictHelper):
    """Manage various bits of metadata for a Vumi Go message.

    Any Go inbound message that has reached the main dispatcher, will already
    have at least `user_account_key` in helper metadata. `conversation_type`
    and `conversation_key` are set once the message gets routed to the
    conversation.

    TODO: Something about non-conversation routers.

    We store metadata in two places:

    1. Keys into the various stores go into the message helper_metadata.
       This is helpful for preventing unnecessary duplicate lookups between
       workers.

    2. Objects retreived from those stores get stashed on the message object.
       This is helpful for preventing duplicate lookups within a worker.
       (Between different middlewares, for example.)

    In addition, use an external conversation cache (if one is provided) to
    allow caching of conversation objects between different messages in the
    same worker.
    """

    def __init__(self, vumi_api, message, conversation_cache=None):
        self.vumi_api = vumi_api
        self.message = message
        self._conversation_cache = conversation_cache

        super(MessageMetadataHelper, self).__init__(
            message.get('helper_metadata', {}))

        # A place to store objects we don't want serialised.
        if not hasattr(message, '_store_objects'):
            message._store_objects = {}
        self._store_objects = message._store_objects

        # If we don't have a tag, we want to blow up early in some places.
        self.tag = TaggingMiddleware.map_msg_to_tag(message)

    def clear_object_cache(self):
        """Clear any cached objects we might have.

        This forces the next get call to fetch the object from the datastore
        again.
        """
        self._store_objects.clear()

    def _stash_and_return_object(self, obj, key):
        self._store_objects[key] = obj
        return obj

    def _get_if_not_stashed(self, key, func, *args, **kw):
        if key in self._store_objects:
            return succeed(self._store_objects[key])
        return func(*args, **kw).addCallback(
            self._stash_and_return_object, key)

    def get_user_api(self):
        return self.vumi_api.get_user_api(self.get_account_key())

    def get_conversation(self):
        if self._conversation_cache is not None:
            getter = lambda key: self._conversation_cache.get_model(
                self.get_user_api().get_wrapped_conversation, key)
        else:
            getter = self.get_user_api().get_wrapped_conversation
        return self._get_if_not_stashed(
            'conversation', getter, self.get_conversation_key())

    def is_optout_message(self):
        # To avoid circular imports.
        from go.vumitools.opt_out.utils import OptOutHelper
        return OptOutHelper.is_optout_message(self.message)

    def get_router(self):
        return self._get_if_not_stashed(
            'router', self.get_user_api().get_router, self.get_router_key())

    def set_tag(self, tag):
        TaggingMiddleware.add_tag_to_msg(self.message, tag)
        self.tag = TaggingMiddleware.map_msg_to_tag(self.message)

    def get_tag_info(self):
        if self.tag is None:
            raise ValueError("No tag to look up metadata for.")

        return self._get_if_not_stashed(
            'tag_info', self.vumi_api.mdb.get_tag_info, tuple(self.tag))

    def get_tagpool_metadata(self):
        if self.tag is None:
            raise ValueError("No tag to look up metadata for.")

        return self._get_if_not_stashed(
            'tagpool_metadata', self.vumi_api.tpm.get_metadata, self.tag[0])
