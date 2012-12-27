import json
import string

from twisted.internet import reactor
from twisted.web import http
from twisted.internet.defer import inlineCallbacks, Deferred, returnValue
from twisted.web.server import Site

from vumi.tests.utils import PersistenceMixin, VumiWorkerTestCase
from vumi.utils import http_request_full

from go.vumitools.api import VumiApi
from go.vumitools.api_resource import GroupsApi, GroupApi
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
        self.contact_store = self.user_api.contact_store

        self.url = 'http://%s:%s' % (self.addr.host, self.addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield super(GroupsApiTestCase, self).tearDown()
        yield self._persist_tearDown()
        self.port.loseConnection()

    def mkurl(self, *parts):
        return '%s/%s' % (self.url, '/'.join(parts))

    def wait_for_results(self, url):
        """
        Keep hitting the URL until it returns an HTTP 200 / OK
        """

        @inlineCallbacks
        def check(d):
            response = yield http_request_full(url, method='GET')
            if response.code == http.OK:
                d.callback(response)
            else:
                reactor.callLater(0, check, d)

        done = Deferred()
        reactor.callLater(0, check, done)
        return done

    @inlineCallbacks
    def test_root(self):
        resp = yield http_request_full(self.mkurl(), method='GET')
        self.assertEqual(resp.code, http.NOT_FOUND)

    @inlineCallbacks
    def test_account_key(self):
        resp = yield http_request_full(self.mkurl(self.user.key), method='GET')
        self.assertEqual(resp.code, http.OK)
        self.assertEqual(resp.headers.getRawHeaders('content-type'),
            ['application/json; charset=utf-8'])
        self.assertEqual(json.loads(resp.delivered_body), [])

    @inlineCallbacks
    def test_invalid_account_key(self):
        resp = yield http_request_full(self.mkurl('foo'), method='GET')
        self.assertEqual(resp.code, http.NOT_FOUND)

    @inlineCallbacks
    def test_group_listings(self):
        yield self.contact_store.new_group(u'group1')
        yield self.contact_store.new_smart_group(u'group2', u'foo:bar')

        resp = yield http_request_full(self.mkurl(self.user.key), method='GET')
        data = json.loads(resp.delivered_body)
        group1, group2 = sorted(data, key=lambda group: group['name'])
        self.assertEqual(group1['name'], 'group1')
        self.assertEqual(group1['query'], None)

        self.assertEqual(group2['name'], 'group2')
        self.assertEqual(group2['query'], 'foo:bar')

    @inlineCallbacks
    def test_group(self):
        group = yield self.contact_store.new_group(u'group1')
        resp = yield http_request_full(self.mkurl(self.user.key, group.key),
                                        method='GET')
        self.assertEqual(resp.code, http.ACCEPTED)
        redis = self.redis.sub_manager('group_api')
        self.assertTrue((yield redis.exists('in_progress:%s-%s' % (
            group.key, 'msisdn'))))

    @inlineCallbacks
    def create_sample_group(self, data=None):
        data = data or [{
                'name': u'aaa',
                'surname': u'nnn',
                'msisdn': u'123',
            }, {
                'name': u'bbb',
                'surname': u'mmm',
                'msisdn': u'456',
            }]
        group = yield self.contact_store.new_group(u'group1')
        # FIXME: For some reason msisdn is not allowed to be null.
        contacts = []
        for data in data:
            contacts.append((yield self.contact_store.new_contact(
                groups=[group], **data)))
        returnValue((group, contacts))

    @inlineCallbacks
    def test_group_default_ordering(self):
        group, (contact1, contact2) = yield self.create_sample_group()
        url = yield self.mkurl(self.user.key, group.key)
        resp = yield self.wait_for_results(url)

        [rc1, rc2] = json.loads(resp.delivered_body)
        self.assertEqual(rc1['key'], contact1.key)
        self.assertEqual(rc2['key'], contact2.key)

    @inlineCallbacks
    def test_group_descending_ordering(self):
        group, (contact1, contact2) = yield self.create_sample_group()
        url = yield self.mkurl(self.user.key, group.key)
        resp = yield self.wait_for_results('%s?ordering=-msisdn' % (url,))

        [rc1, rc2] = json.loads(resp.delivered_body)
        self.assertEqual(rc1['key'], contact2.key)
        self.assertEqual(rc2['key'], contact1.key)

    @inlineCallbacks
    def test_group_order_by_name(self):
        (group, (contact1, contact2)) = yield self.create_sample_group()
        url = yield self.mkurl(self.user.key, group.key)
        resp = yield self.wait_for_results('%s?ordering=name' % (url,))

        [rc1, rc2] = json.loads(resp.delivered_body)
        self.assertEqual(rc1['key'], contact1.key)
        self.assertEqual(rc2['key'], contact2.key)

    @inlineCallbacks
    def test_group_order_by_surname(self):
        (group, (contact1, contact2)) = yield self.create_sample_group()
        url = yield self.mkurl(self.user.key, group.key)
        resp = yield self.wait_for_results('%s?ordering=surname' % (url,))

        [rc1, rc2] = json.loads(resp.delivered_body)
        self.assertEqual(rc1['key'], contact2.key)
        self.assertEqual(rc2['key'], contact1.key)

    @inlineCallbacks
    def test_group_order_by_name_surname_msisdn(self):
        group, contacts = yield self.create_sample_group([{
                'name': u'aaa',
                'surname': u'bbb',
                'msisdn': u'345',
            }, {
                'name': u'aaa',
                'surname': u'bbb',
                'msisdn': u'234',
            }, {
                'name': u'aaa',
                'surname': u'bbb',
                'msisdn': u'123',
            }])
        url = yield self.mkurl(self.user.key, group.key)
        resp = yield self.wait_for_results(
            '%s?ordering=name&ordering=surname&ordering=msisdn' % (url,))

        [contact1, contact2, contact3] = contacts
        [rc1, rc2, rc3] = json.loads(resp.delivered_body)
        self.assertEqual(rc1['key'], contact3.key)
        self.assertEqual(rc2['key'], contact2.key)
        self.assertEqual(rc3['key'], contact1.key)

    @inlineCallbacks
    def test_group_order_by_name_surname_msisdn_descending(self):
        group, contacts = yield self.create_sample_group([{
                'name': u'aaa',
                'surname': u'bbb',
                'msisdn': u'345',
            }, {
                'name': u'aaa',
                'surname': u'bbb',
                'msisdn': u'234',
            }, {
                'name': u'aaa',
                'surname': u'bbb',
                'msisdn': u'123',
            }])
        url = yield self.mkurl(self.user.key, group.key)
        resp = yield self.wait_for_results(
            '%s?ordering=-name&ordering=-surname&ordering=-msisdn' % (url,))

        [contact1, contact2, contact3] = contacts
        [rc1, rc2, rc3] = json.loads(resp.delivered_body)
        self.assertEqual(rc1['key'], contact1.key)
        self.assertEqual(rc2['key'], contact2.key)
        self.assertEqual(rc3['key'], contact3.key)

    @inlineCallbacks
    def test_pagination(self):
        group, contacts = yield self.create_sample_group(
            [{'name': letter, 'msisdn': u''} for letter in u'abcd'])
        [c1, c2, c3, c4] = contacts

        url = yield self.mkurl(self.user.key, group.key)
        page1_resp = yield self.wait_for_results(
            '%s?ordering=name&start=0&stop=1' % (url,))

        [rc1, rc2] = json.loads(page1_resp.delivered_body)
        self.assertEqual(rc1['key'], c1.key)
        self.assertEqual(rc2['key'], c2.key)

        page2_resp = yield self.wait_for_results(
            '%s?ordering=name&start=2&stop=3' % (url,))

        [rc3, rc4] = json.loads(page2_resp.delivered_body)
        self.assertEqual(rc3['key'], c3.key)
        self.assertEqual(rc4['key'], c4.key)

    @inlineCallbacks
    def test_pagination_reverse(self):
        group, contacts = yield self.create_sample_group(
            [{'name': letter, 'msisdn': u''} for letter in u'abcd'])
        [c1, c2, c3, c4] = contacts

        url = yield self.mkurl(self.user.key, group.key)
        page1_resp = yield self.wait_for_results(
            '%s?ordering=-name&start=0&stop=1' % (url,))

        [rc1, rc2] = json.loads(page1_resp.delivered_body)
        self.assertEqual(rc1['key'], c4.key)
        self.assertEqual(rc2['key'], c3.key)

        page2_resp = yield self.wait_for_results(
            '%s?ordering=-name&start=2&stop=3' % (url,))

        [rc3, rc4] = json.loads(page2_resp.delivered_body)
        self.assertEqual(rc3['key'], c2.key)
        self.assertEqual(rc4['key'], c1.key)

    @inlineCallbacks
    def test_counts(self):
        group, contacts = yield self.create_sample_group(
            [{'name': letter, 'msisdn': u''}
                for letter in unicode(string.lowercase)])
        url = yield self.mkurl(self.user.key, group.key)
        resp = yield self.wait_for_results(url)
        self.assertEqual(resp.headers.getRawHeaders(
            GroupApi.RESP_COUNT_HEADER), ['26'])
        self.assertEqual(len(json.loads(resp.delivered_body)), 26)
