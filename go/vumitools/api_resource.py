# -*- test-case-name: go.vumitools.tests.test_api_resource -*-

import json
from datetime import datetime

from twisted.web import resource, http
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import inlineCallbacks, returnValue


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
        collection = []
        bunches = proxy.load_all_bunches(keys)
        for bunch in bunches:
            collection.extend((yield bunch))
        returnValue(collection)


class GroupApi(BaseResource):
    """
    Return the members of a specific group
    """
    def __init__(self, user_api, group_key):
        BaseResource.__init__(self)
        self.user_api = user_api
        self.contact_store = self.user_api.contact_store
        self.group_key = group_key

    @inlineCallbacks
    def _render_group(self, request):
        group = yield self.contact_store.get_group(self.group_key)
        if group is None:
            request.code = http.NOT_FOUND
            request.finish()
            return

        contact_keys = yield self.contact_store.get_contacts_for_group(group)
        contacts = yield self.load_bunches(self.contact_store.contacts,
                                            contact_keys)

        request.responseHeaders.setRawHeaders('content-type',
                                                [self.CONTENT_TYPE])

        request.write(self.to_json([dict(c) for c in contacts]))
        request.finish()

    def render_GET(self, request):
        self._render_group(request)
        return NOT_DONE_YET


class AccountGroupsApi(BaseResource):

    def __init__(self, user_api):
        """
        An HTTP API to provide access to groups for a specific account stored
        in Riak.

        :param VumiUserApi user_api:
            The account api to fetch groups from.
        """
        BaseResource.__init__(self)
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
        request.write(self.to_json([dict(gr) for gr in groups]))
        request.finish()

    def render_GET(self, request):
        self._render_groups(request)
        return NOT_DONE_YET

    def getChild(self, group_key, request):
        if group_key:
            return GroupApi(self.user_api, group_key)
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

    def getChild(self, account_key, request):
        if account_key:
            return AccountGroupsApi(self.api.get_user_api(account_key))
        return resource.NoResource()
