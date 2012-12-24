# -*- test-case-name: go.vumitools.tests.test_api_resource -*-

import json

from twisted.web import resource, http
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import inlineCallbacks


class AccountGroupsApi(resource.Resource):

    CONTENT_TYPE = 'application/json; charset=utf-8'

    def __init__(self, user_api):
        """
        An HTTP API to provide access to groups for a specific account stored
        in Riak.

        :param VumiUserApi user_api:
            The account api to fetch groups from.
        """
        resource.Resource.__init__(self)
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
        request.write(json.dumps(groups))
        request.finish()

    def render_GET(self, request):
        self._render_groups(request)
        return NOT_DONE_YET


class GroupsApi(resource.Resource):
    def __init__(self, api):
        """
        An HTTP API to provide access to groups for accounts stored in Riak

        :param VumiApi api:
            A Vumi API object.
        """
        resource.Resource.__init__(self)
        self.api = api

    def getChild(self, account_key, request):
        if account_key:
            return AccountGroupsApi(self.api.get_user_api(account_key))
        return resource.NoResource()
