class PagedMessageCacheException(Exception):
    pass


class PagedMessageCache(object):
    """
    A view on keys in the MessageStoreCache that's compatible
    with Django's Paginator class.
    """

    def __init__(self, count, callback):
        self.count = count
        self.callback = callback

    def __len__(self):
        """
        Return the total number of available results without actually
        returning the full set.
        """
        return self.count

    def __getitem__(self, value):
        if isinstance(value, slice):
            if not value.step:
                return self.callback(value.start, value.stop)
        raise PagedMessageCacheException(
            'Only `[start:stop]` slices accepted.')
