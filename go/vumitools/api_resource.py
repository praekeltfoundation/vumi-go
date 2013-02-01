# -*- test-case-name: go.vumitools.tests.test_api_resource -*-

import json
from datetime import datetime

from twisted.web import resource, http
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import inlineCallbacks, returnValue

from go.base.utils import multikeysort


class ResourceJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(ResourceJSONEncoder, self).default(obj)


class BaseResource(resource.Resource):

    CONTENT_TYPE = 'application/json; charset=utf-8'
    JSON_ENCODER = ResourceJSONEncoder

    def to_json(self, models):
        """
        Turn stuff vumi.persist.Model gives us into JSON
        """
        return json.dumps(models, cls=self.JSON_ENCODER)

    @inlineCallbacks
    def load_bunches(self, proxy, keys):
        """
        Load bunches while preserving the order of the keys.
        """
        collection = []
        bunches = proxy.load_all_bunches(keys)
        for bunch in bunches:
            collection.extend((yield bunch))
        returnValue(sorted(collection, key=lambda c: keys.index(c.key)))


class GroupApi(BaseResource):
    """
    Return the members of a specific group
    """

    DEFAULT_ORDERING = 'msisdn'

    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'

    RESP_COUNT_HEADER = 'X-VGo-Group-Count'
    REQ_WAIT_HEADER = 'X-VGo-Group-Wait-Results'

    def __init__(self, redis, user_api, group_key):
        BaseResource.__init__(self)
        self.redis = redis
        self.user_api = user_api
        self.store = self.user_api.contact_store
        self.group_key = group_key

    def get_progress_key(self, ordering):
        # Joining on '+' because '-' can be part of the ordering key.
        order_key = '+'.join(ordering)
        return 'in_progress:%s-%s' % (self.group_key, order_key)

    def set_in_progress(self, ordering, in_progress):
        progress_key = self.get_progress_key(ordering)
        if in_progress:
            return self.redis.set(progress_key, 1)
        return self.redis.set(progress_key, 0)

    @inlineCallbacks
    def is_in_progress(self, ordering):
        status = yield self.redis.get(self.get_progress_key(ordering))
        if status is None:
            returnValue(False)
        returnValue(bool(int(status)))

    def get_results_key(self, ordering):
        # Joining on '+' because '-' can be part of the ordering key.
        order_key = '+'.join(ordering)
        return 'results_key:%s-%s' % (self.group_key, order_key)

    def has_results(self, ordering):
        return self.redis.exists(self.get_results_key(ordering))

    @inlineCallbacks
    def cache_contacts(self, ordering):
        yield self.set_in_progress(ordering, True)
        contact_keys = yield self.store.get_contacts_for_group(self.group)
        contacts = yield self.load_bunches(self.store.contacts, contact_keys)
        sorted_contacts = multikeysort([c.get_data() for c in contacts],
                                        ordering)
        results_key = self.get_results_key(ordering)
        for contact in sorted_contacts:
            yield self.redis.rpush(results_key, contact['key'])
        yield self.set_in_progress(ordering, False)

    @inlineCallbacks
    def render_results(self, request, ordering):
        result_key = self.get_results_key(ordering)
        start = (int(request.args['start'][0])
                    if 'start' in request.args else 0)
        stop = (int(request.args['stop'][0])
                if 'stop' in request.args else -1)
        contact_keys = yield self.redis.lrange(result_key, start, stop)
        contacts = yield self.load_bunches(self.store.contacts, contact_keys)
        request.responseHeaders.setRawHeaders(self.RESP_COUNT_HEADER,
            [(yield self.redis.llen(result_key))])
        request.responseHeaders.setRawHeaders('content-type',
                                                [self.CONTENT_TYPE])
        request.write(self.to_json([c.get_data() for c in contacts]))
        request.finish()

    @inlineCallbacks
    def get_status(self, ordering):
        """
        Check whether or not we have results available for a specific order.
        """
        if (yield self.is_in_progress(ordering)):
            returnValue(self.STATUS_IN_PROGRESS)
        if (yield self.has_results(ordering)):
            returnValue(self.STATUS_DONE)

    @inlineCallbacks
    def render_group(self, request):
        self.group = yield self.store.get_group(self.group_key)
        if self.group is None:
            request.code = http.NOT_FOUND
            request.finish()
            return

        ordering = (request.args['ordering']
                        if 'ordering' in request.args
                        else [self.DEFAULT_ORDERING])

        status = yield self.get_status(ordering)
        if status == self.STATUS_DONE:
            self.render_results(request, ordering)
            return

        if status != self.STATUS_IN_PROGRESS:
            wait_for_completion = self.cache_contacts(ordering)
            headers = request.requestHeaders
            if headers.hasHeader(self.REQ_WAIT_HEADER):
                wait = bool(int(
                            headers.getRawHeaders(self.REQ_WAIT_HEADER)[0]))
            else:
                wait = False

            if wait:
                yield wait_for_completion
                yield self.render_results(request, ordering)
                return

        request.code = http.ACCEPTED
        request.finish()

    def render_GET(self, request):
        self.render_group(request)
        return NOT_DONE_YET


class AccountGroupsApi(BaseResource):

    def __init__(self, redis, user_api):
        """
        An HTTP API to provide access to groups for a specific account stored
        in Riak.

        :param VumiUserApi user_api:
            The account api to fetch groups from.
        """
        BaseResource.__init__(self)
        self.redis = redis
        self.user_api = user_api

    @inlineCallbacks
    def _render_groups(self, request):
        if not (yield self.user_api.exists()):
            request.code = http.NOT_FOUND
            request.finish()
            return

        groups = yield self.user_api.list_groups()
        request.responseHeaders.setRawHeaders('content-type',
                                                [self.CONTENT_TYPE])
        request.write(self.to_json([gr.get_data() for gr in groups]))
        request.finish()

    def render_GET(self, request):
        self._render_groups(request)
        return NOT_DONE_YET

    def getChild(self, group_key, request):
        if group_key:
            return GroupApi(self.redis, self.user_api, group_key)
        return self


class GroupsApi(BaseResource):
    def __init__(self, api):
        """
        An HTTP API to provide access to groups for accounts stored in Riak

        :param VumiApi api:
            A Vumi API object.
        """
        BaseResource.__init__(self)
        self.api = api
        self.redis = api.redis.sub_manager('group_api')

    def getChild(self, account_key, request):
        if account_key:
            return AccountGroupsApi(self.redis,
                                    self.api.get_user_api(account_key))
        return resource.NoResource()
