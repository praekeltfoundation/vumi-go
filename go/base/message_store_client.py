import requests
import json

from django.core.paginator import Paginator

from vumi.message import TransportUserMessage


class ClientException(Exception):
    pass


class Client(object):

    def __init__(self, base_url):
        self.base_url = base_url

    def do_get(self, path, params):
        url = '%s%s' % (self.base_url, path)
        return requests.get(url, params=params)

    def do_post(self, path, data):
        url = '%s%s' % (self.base_url, path)
        return requests.post(url, data=data)

    def match(self, batch_id, direction, query):
        path = 'batch/%s/%s/match/' % (batch_id, direction)
        response = self.do_post(path, data=json.dumps(query))
        return response.headers['x-vms-result-token']

    def get_match_results(self, batch_id, direction, token, page=None,
                            page_size=None):
        return MatchResult(self, batch_id, direction, token, page,
                            page_size)


class MatchResult(object):
    def __init__(self, client, base_url, batch_id, direction, token, page=1,
        page_size=20):
        self.client = client
        self.base_url = base_url
        self.batch_id = batch_id
        self.direction = direction
        self.token = token
        self.page = page
        self.page_size = page_size
        self.paginator = None
        self.path = 'batch/%s/%s/match/' % (batch_id, direction)
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
        # Allows for this class to be used as input for a Django Paginator
        if isinstance(value, slice):
            if not value.step:
                return self.get_slice(value.start, value.stop)
        raise ClientException(
            'Only `[start:stop]` slices accepted.')

    def get_slice(self, start, stop):
        # We're doing very simple caching here since we need to get at least
        # one page to get the total count and whether or not the stuff is still
        # in progress or not.
        cache_key = self._cache_key(start, stop)
        cache_hit = self._cache.get(cache_key)
        if cache_hit is not None:
            return cache_hit

        response = self.client.do_get(self.path, params={
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
            raise ClientException(
                'count() called before page load.')
        return self._total_count

    def is_in_progress(self):
        if self._in_progress is None:
            raise ClientException(
                'is_in_progress() called before page load.')
        return self._in_progress

    def __repr__(self):
        return "<MatchResult in_progress: %s, total_count: %s>" % (
            self._in_progress, self._total_count)
