import requests
import json

from django.core.paginator import Page, Paginator

from vumi.message import TransportUserMessage


class PagedMessageCacheException(Exception):
    pass


class MessageStoreClientException(Exception):
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


class MessageStoreClient(object):

    def __init__(self, base_url):
        self.base_url = base_url

    def match(self, batch_id, direction, query):
        url = '%sbatch/%s/%s/match/' % (self.base_url, batch_id, direction)
        response = requests.post(url, data=json.dumps(query))
        return response.headers['x-vms-result-token']

    def get_match_results(self, batch_id, direction, token, page=None,
                            page_size=None):
        return MatchResult(self.base_url, batch_id, direction, token, page,
                            page_size)


class MatchResult(object):
    def __init__(self, base_url, batch_id, direction, token, page=1,
        page_size=20):
        self.base_url = base_url
        self.batch_id = batch_id
        self.direction = direction
        self.token = token
        self.page = page
        self.page_size = page_size
        self.paginator = None
        self.url = '%sbatch/%s/%s/match/' % (self.base_url, batch_id,
                                                direction)
        self._total_count = None
        self._in_progress = None
        self._cache = {}
        if self.page and self.page_size:
            # NOTE:
            # We do this here because we need to first load a page
            # to see what the total result count is before we can paginate.
            # The results are cached so if one provides the correct page
            # number up front there is no performance penalty
            start = (self.page - 1) * self.page_size
            stop = start + self.page_size
            self.get_slice(start, stop)
            # Make a paginator with the right page size set available for
            # convenience.
            self.paginator = Paginator(self, self.page_size)

    def _cache_key(self, start, stop):
        return '%s-%s' % (start, stop)

    def __getitem__(self, value):
        if isinstance(value, slice):
            if not value.step:
                return self.get_slice(value.start, value.stop)
        raise MessageStoreClientException(
            'Only `[start:stop]` slices accepted.')

    def get_slice(self, start, stop):
        # We're doing very simple caching here since we need to get at least
        # one page to get the total count and whether or not the stuff is still
        # in progress or not.
        cache_key = self._cache_key(start, stop)
        cache_hit = self._cache.get(cache_key)
        if cache_hit is not None:
            return cache_hit

        response = requests.get(self.url, params={
            'token': self.token,
            'start': start,
            'stop': stop,
        })
        self._in_progress = bool(int(
                                response.headers['x-vms-match-in-progress']))
        self._total_count = int(response.headers['x-vms-result-count'])
        results = [self.mk_message(payload) for payload in response.json]
        # If we get less results back that the page_size then rewrite
        # the cache key to prevent a cache miss.
        if len(results) < (stop - start):
            cache_key = self._cache_key(start, len(results))
        self._cache[cache_key] = results
        return results

    def mk_message(self, dictionary):
        return TransportUserMessage(_process_fields=False, **dictionary)

    def count(self):
        # Django Paginator calls this.
        if self._total_count is None:
            raise MessageStoreClientException(
                'count() called before page load.')
        return self._total_count

    def is_in_progress(self):
        if self._in_progress is None:
            raise MessageStoreClientException(
                'is_in_progress() called before page load.')
        return self._in_progress

    def __repr__(self):
        return "<MatchResult in_progress: %s, total_count: %s>" % (
            self._in_progress, self._total_count)
