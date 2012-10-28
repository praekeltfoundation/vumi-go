class PagedMessageCacheException(Exception):
    pass


class PagedMessageCache(object):
    """
    A view on keys in the MessageStoreCache that's compatible
    with Django's Paginator class.
    """

    def __init__(self, conversation, direction, batch_id=None):
        self.batch_id = batch_id
        if direction == 'inbound':
            self.count_callback = conversation.count_replies
            self.messages_callback = conversation.replies
        elif direction == 'outbound':
            self.count_callback = conversation.count_sent_messages
            self.messages_callback = conversation.sent_messages
        else:
            raise PagedMessageCacheException('Unknown direction: %s' % (
                direction,))

    def __len__(self):
        """
        Return the total number of available results without actually
        returning the full set.
        """
        return self.count_callback(self.batch_id)

    def __getitem__(self, value):
        if isinstance(value, slice):
            if not value.step:
                return self.messages_callback(value.start, value.stop,
                    self.batch_id)
        raise PagedMessageCacheException(
            'Only `[start:stop]` slices accepted.')
