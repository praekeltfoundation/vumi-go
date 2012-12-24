import json

from twisted.internet import reactor
from twisted.web import http
from twisted.internet.defer import inlineCallbacks
from twisted.web.server import Site

from vumi.tests.utils import PersistenceMixin, VumiWorkerTestCase
from vumi.utils import http_request_full

from go.vumitools.api import VumiApi
from go.vumitools.api_resource import GroupsApi
from go.vumitools.account.models import AccountStore


class GroupsApiTestCase(VumiWorkerTestCase, PersistenceMixin):

    use_riak = True
    timeout = 5

    @inlineCallbacks
    def setUp(self):
        yield super(GroupsApiTestCase, self).setUp()
        self._persist_setUp()
        self.riak = yield self.get_riak_manager()
        self.redis = yield self.get_redis_manager()
        self.api = VumiApi(self.riak, self.redis)
        self.resource = GroupsApi(self.api)
        self.site = Site(self.resource)
        self.port = reactor.listenTCP(0, self.site)
        self.addr = self.port.getHost()

        self.account_store = AccountStore(self.riak)
        self.user = yield self.account_store.new_user(username=u'username')
        self.user_api = self.api.get_user_api(self.user.key)

        self.url = 'http://%s:%s' % (self.addr.host, self.addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield super(GroupsApiTestCase, self).tearDown()
        yield self._persist_tearDown()
        self.port.loseConnection()

    def mkurl(self, *parts):
        return '%s/%s' % (self.url, '/'.join(parts))

    @inlineCallbacks
    def test_root(self):
        resp = yield http_request_full(self.mkurl(), method='GET')
        self.assertEqual(resp.code, http.NOT_FOUND)

    @inlineCallbacks
    def test_account_key(self):
        resp = yield http_request_full(self.mkurl(self.user.key), method='GET')
        self.assertEqual(resp.code, http.OK)
        self.assertEqual(resp.headers.getRawHeaders('content-type'), [
            'application/json; charset=utf-8'])
        self.assertEqual(json.loads(resp.delivered_body), [])

    @inlineCallbacks
    def test_invalid_account_key(self):
        resp = yield http_request_full(self.mkurl('foo'), method='GET')
        self.assertEqual(resp.code, http.NOT_FOUND)
