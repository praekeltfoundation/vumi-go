# -*- test-case-name: go.vumitools.channel.tests.test_models -*-

from go.vumitools.account import PerAccountStore
from go.vumitools.routing_table import GoConnector


class FakeForeignKey(object):
    def __init__(self, key):
        self.key = key


class CheapPlasticChannel(object):
    """Thin wrapper around a tagpool+tag.

    TODO: Replace this with an actual channel object.
    """

    def __init__(self, tagpool, tag, tagpool_metadata, batch_id):
        self.tagpool = tagpool
        self.tag = tag
        self.tagpool_metadata = tagpool_metadata
        self.key = u'%s:%s' % (tagpool, tag)
        self.name = tag
        self.batch = FakeForeignKey(batch_id)

    def release(self, user_api):
        user_api.release_tag((self.tagpool, self.tag))

    def _check_support(self, option):
        supports = self.tagpool_metadata.get('supports', {})
        return bool(supports.get(option))

    def supports(self, **kw):
        return all(self._check_support(option) == value
                   for option, value in kw.iteritems())

    def supports_generic_sends(self):
        return self._check_support('generic_sends')

    def supports_replies(self):
        return self._check_support('replies')

    def get_connector(self):
        return GoConnector.for_transport_tag(self.tagpool, self.tag)


class ChannelStore(PerAccountStore):
    # TODO: This is a mostly a placeholder until we have a real
    #       channel model.

    def get_channel_by_tag(self, tag, tagpool_metadata, batch_id):
        """Return the active channel within this account for the given tag.

        Returns `None` if no such channel exists.
        """
        return CheapPlasticChannel(tag[0], tag[1], tagpool_metadata, batch_id)
