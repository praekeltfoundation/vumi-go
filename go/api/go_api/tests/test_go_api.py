"""Tests for go.api.go_api.go_api"""

from xmlrpclib import METHOD_NOT_FOUND

from txjsonrpc.web.jsonrpc import Proxy
from txjsonrpc.jsonrpclib import Fault

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.server import Site

from vumi.utils import http_request

from go.vumitools.account.models import GoConnector, RoutingTableHelper
from go.vumitools.tests.utils import AppWorkerTestCase
from go.api.go_api.api_types import RoutingEntryType, EndpointType
from go.api.go_api.go_api import GoApiWorker, GoApiServer


class GoApiServerTestCase(AppWorkerTestCase):

    worker_name = 'GoApiServer'
    transport_name = 'sphex'
    transport_type = 'sphex_type'

    @inlineCallbacks
    def setUp(self):
        super(GoApiServerTestCase, self).setUp()
        self.vumi_api = yield self.get_vumi_api()
        self.account = yield self.mk_user(self.vumi_api, u'user')
        self.user_api = self.vumi_api.get_user_api(self.account.key)
        self.campaign_key = self.account.key

        site = Site(GoApiServer(self.account.key, self.vumi_api))
        self.server = yield reactor.listenTCP(0, site)
        addr = self.server.getHost()
        self.proxy = Proxy("http://%s:%d/" % (addr.host, addr.port))

    @inlineCallbacks
    def tearDown(self):
        yield self.server.loseConnection()
        yield super(GoApiServerTestCase, self).tearDown()

    @inlineCallbacks
    def assert_faults(self, d, fault_code, fault_string):
        try:
            yield d
        except Fault, e:
            self.assertEqual(e.faultString, fault_string)
            self.assertEqual(e.faultCode, fault_code)
        else:
            self.fail("Expected fault %s: %s." % (fault_code, fault_string))

    @inlineCallbacks
    def test_campaigns(self):
        result = yield self.proxy.callRemote("campaigns")
        self.assertEqual(result, [
            {'key': self.campaign_key, 'name': u'Your Campaign'},
        ])

    @inlineCallbacks
    def test_conversations(self):
        conv = yield self.user_api.new_conversation(
            u'jsbox', u'My Conversation', u'A description', {})
        result = yield self.proxy.callRemote(
            "conversations", self.campaign_key)
        self.assertEqual(result, [
            {
                'uuid': conv.key,
                'type': conv.conversation_type,
                'name': conv.name,
                'description': conv.description,
                'endpoints': [
                    {
                        u'name': u'default',
                        u'uuid': u'CONVERSATION:jsbox:%s::default' % conv.key,
                    },
                ],
            },
        ])

    @inlineCallbacks
    def test_conversation_with_extra_endpoints(self):
        conv = yield self.user_api.new_conversation(
            u'jsbox', u'My Conversation', u'A description', {},
            extra_endpoints=[u'foo', u'bar'])
        result = yield self.proxy.callRemote(
            "conversations", self.campaign_key)
        self.assertEqual(result, [
            {
                'uuid': conv.key,
                'type': conv.conversation_type,
                'name': conv.name,
                'description': conv.description,
                'endpoints': [
                    {
                        u'name': u'default',
                        u'uuid': u'CONVERSATION:%s:%s::default' % (
                            conv.conversation_type, conv.key),
                    },
                    {
                        u'name': u'foo',
                        u'uuid': u'CONVERSATION:%s:%s::foo' % (
                            conv.conversation_type, conv.key),
                    },
                    {
                        u'name': u'bar',
                        u'uuid': u'CONVERSATION:%s:%s::bar' % (
                            conv.conversation_type, conv.key),
                    },
                ],
            },
        ])

    @inlineCallbacks
    def test_conversations_with_no_conversations(self):
        result = yield self.proxy.callRemote(
            "conversations", self.campaign_key)
        self.assertEqual(result, [])

    @inlineCallbacks
    def test_channels(self):
        yield self.setup_tagpool(u"pool", [u"tag1", u"tag2"])
        yield self.user_api.acquire_tag(u"pool")  # acquires tag1
        result = yield self.proxy.callRemote(
            "channels", self.campaign_key)
        self.assertEqual(result, [
            {
                u'uuid': u'pool:tag1',
                u'name': u'tag1',
                u'tag': [u'pool', u'tag1'],
                u'description': u'Pool: tag1',
                u'endpoints': [
                    {
                        u'name': u'default',
                        u'uuid': u'TRANSPORT_TAG:pool:tag1::default'
                    },
                ],
            },
        ])

    @inlineCallbacks
    def test_routers_with_no_routers(self):
        result = yield self.proxy.callRemote(
            "routers", self.campaign_key)
        self.assertEqual(result, [])

    def _router_endpoint(self, router, name_with_direction):
        return {
            u'name': name_with_direction.split('::', 1)[1],
            u'uuid': u'ROUTER:%s:%s:%s' % (
                router.router_type, router.key, name_with_direction),
        }

    @inlineCallbacks
    def test_routers(self):
        router = yield self.user_api.new_router(
            u'keyword', u'My Router', u'A description', {})
        result = yield self.proxy.callRemote("routers", self.campaign_key)
        self.assertEqual(result, [
            {
                'uuid': router.key,
                'type': router.router_type,
                'name': router.name,
                'description': router.description,
                'channel_endpoints': [
                    self._router_endpoint(router, 'INBOUND::default'),
                ],
                'conversation_endpoints': [
                    self._router_endpoint(router, 'OUTBOUND::default'),
                ],
            },
        ])

    @inlineCallbacks
    def test_routers_with_extra_endpoints(self):
        router = yield self.user_api.new_router(
            u'keyword', u'My Router', u'A description', {},
            extra_inbound_endpoints=[u'foo'],
            extra_outbound_endpoints=[u'bar'])
        result = yield self.proxy.callRemote("routers", self.campaign_key)
        self.assertEqual(result, [
            {
                'uuid': router.key,
                'type': router.router_type,
                'name': router.name,
                'description': router.description,
                'channel_endpoints': [
                    self._router_endpoint(router, 'INBOUND::default'),
                    self._router_endpoint(router, 'INBOUND::foo'),
                ],
                'conversation_endpoints': [
                    self._router_endpoint(router, 'OUTBOUND::default'),
                    self._router_endpoint(router, 'OUTBOUND::bar'),
                ],
            },
        ])

    @inlineCallbacks
    def _connect_conversation_to_tag_through_router(self, conv, tag, router):
        conv_conn = str(GoConnector.for_conversation(
            conv.conversation_type, conv.key))
        channel_conn = str(GoConnector.for_transport_tag(*tag))
        router_in_conn = str(GoConnector.for_router(
            router.router_type, router.key, GoConnector.INBOUND))
        router_out_conn = str(GoConnector.for_router(
            router.router_type, router.key, GoConnector.OUTBOUND))
        user_account = yield self.user_api.get_user_account()
        rt_helper = RoutingTableHelper(user_account.routing_table)
        rt_helper.add_entry(
            channel_conn, 'default', router_in_conn, 'default')
        rt_helper.add_entry(router_out_conn, 'default', conv_conn, 'default')
        rt_helper.add_entry(conv_conn, 'default', router_out_conn, 'default')
        rt_helper.add_entry(router_in_conn, 'default', channel_conn, 'default')
        rt_helper.validate_all_entries()
        yield user_account.save()

    @inlineCallbacks
    def _setup_routing_table(self):
        conv = yield self.user_api.new_conversation(
            u'jsbox', u'My Conversation', u'A description', {})
        router = yield self.user_api.new_router(
            u'keyword', u'My Router', u'A description', {})
        yield self.setup_tagpool(u"pool", [u"tag1", u"tag2"])
        tag = yield self.user_api.acquire_tag(u"pool")  # acquires tag1
        yield self._connect_conversation_to_tag_through_router(
            conv, tag, router)
        returnValue((conv, router, tag))

    @inlineCallbacks
    def test_routing_entries(self):
        conv, router, tag = yield self._setup_routing_table()
        result = yield self.proxy.callRemote(
            "routing_entries", self.campaign_key)
        result.sort(key=lambda x: x['source']['uuid'])
        self.assertEqual(result, [
            {
                u'source': {u'uuid': u'CONVERSATION:jsbox:%s::default'
                            % conv.key},
                u'target': {u'uuid': u'ROUTER:keyword:%s:OUTBOUND::default'
                            % router.key},
            },
            {
                u'source': {u'uuid': u'ROUTER:keyword:%s:INBOUND::default'
                            % router.key},
                u'target': {u'uuid': u'TRANSPORT_TAG:pool:tag1::default'}
            },
            {
                u'source': {u'uuid': u'ROUTER:keyword:%s:OUTBOUND::default'
                            % router.key},
                u'target': {u'uuid': u'CONVERSATION:jsbox:%s::default'
                            % conv.key},
            },
            {
                u'source': {u'uuid': u'TRANSPORT_TAG:pool:tag1::default'},
                u'target': {u'uuid': u'ROUTER:keyword:%s:INBOUND::default'
                            % router.key},
            },
        ])

    @inlineCallbacks
    def test_routing_table(self):
        conv, router, tag = yield self._setup_routing_table()
        result = yield self.proxy.callRemote(
            "routing_table", self.campaign_key)
        result['routing_entries'].sort(key=lambda x: x['source']['uuid'])
        self.assertEqual(result, {
            u'channels': [
                {
                    u'uuid': u'pool:tag1',
                    u'name': u'tag1',
                    u'tag': [u'pool', u'tag1'],
                    u'description': u'Pool: tag1',
                    u'endpoints': [
                        {
                            u'name': u'default',
                            u'uuid': u'TRANSPORT_TAG:pool:tag1::default',
                        }
                    ],
                }
            ],
            u'conversations': [
                {
                    u'uuid': conv.key,
                    u'type': conv.conversation_type,
                    u'name': conv.name,
                    u'description': conv.description,
                    u'endpoints': [
                        {
                            u'name': u'default',
                            u'uuid': u'CONVERSATION:jsbox:%s::default'
                            % conv.key,
                        },
                    ],
                }
            ],
            u'routers': [
                {
                    'uuid': router.key,
                    'type': router.router_type,
                    'name': router.name,
                    'description': router.description,
                    'channel_endpoints': [
                        self._router_endpoint(router, 'INBOUND::default'),
                    ],
                    'conversation_endpoints': [
                        self._router_endpoint(router, 'OUTBOUND::default'),
                    ],
                },
            ],
            u'routing_entries': [
                {
                    u'source': {u'uuid': u'CONVERSATION:jsbox:%s::default'
                                % conv.key},
                    u'target': {u'uuid': u'ROUTER:keyword:%s:OUTBOUND::default'
                                % router.key},
                },
                {
                    u'source': {u'uuid': u'ROUTER:keyword:%s:INBOUND::default'
                                % router.key},
                    u'target': {u'uuid': u'TRANSPORT_TAG:pool:tag1::default'}
                },
                {
                    u'source': {u'uuid': u'ROUTER:keyword:%s:OUTBOUND::default'
                                % router.key},
                    u'target': {u'uuid': u'CONVERSATION:jsbox:%s::default'
                                % conv.key},
                },
                {
                    u'source': {u'uuid': u'TRANSPORT_TAG:pool:tag1::default'},
                    u'target': {u'uuid': u'ROUTER:keyword:%s:INBOUND::default'
                                % router.key},
                },
            ],
        })

    def mk_routing_entry(self, source, target):
        return RoutingEntryType.format_entry(source, target)

    def mk_routing_table(self, entries):
        return {
            'channels': [], 'conversations': [], 'routers': [],
            'routing_entries': [self.mk_routing_entry(*e) for e in entries],
        }

    @inlineCallbacks
    def test_update_routing_table_with_bad_source_endpoint(self):
        conv, router, tag = yield self._setup_routing_table()
        routing_table = self.mk_routing_table([
            (('foo', 'bar'), ('TRANSPORT_TAG:pool:tag1', 'default')),
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        yield self.assert_faults(
            d, 400, "Unknown source endpoint {u'uuid': u'foo::bar'}")

    @inlineCallbacks
    def test_update_routing_table_with_bad_target_endpoint(self):
        conv, router, tag = yield self._setup_routing_table()
        routing_table = self.mk_routing_table([
            (('TRANSPORT_TAG:pool:tag1', 'default'), ('bar', 'baz')),
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        yield self.assert_faults(
            d, 400, u"Source outbound-receiving endpoint {u'uuid':"
            " u'TRANSPORT_TAG:pool:tag1::default'}"
            " should link to an inbound-receiving endpoint"
            " but links to {u'uuid': u'bar::baz'}")

    @inlineCallbacks
    def test_update_routing_table_with_channel_linked_to_itself(self):
        conv, router, tag = yield self._setup_routing_table()
        source = (u'TRANSPORT_TAG:pool:tag1', u'default')
        endpoint_uuid = EndpointType.format_uuid(*source)
        routing_table = self.mk_routing_table([
            (source, source),
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        yield self.assert_faults(
            d, 400, u"Source outbound-receiving endpoint"
            " {u'uuid': %r} should link"
            " to an inbound-receiving endpoint but links to {u'uuid':"
            " %r}"
            % (endpoint_uuid, endpoint_uuid))

    @inlineCallbacks
    def test_update_routing_table_with_conversation_linked_to_itself(self):
        conv, router, tag = yield self._setup_routing_table()
        source = (u'CONVERSATION:%s:%s' % (conv.conversation_type, conv.key),
                  u'default')
        endpoint_uuid = EndpointType.format_uuid(*source)
        routing_table = self.mk_routing_table([
            (source, source),
        ])
        d = self.proxy.callRemote(
                "update_routing_table", self.campaign_key, routing_table)
        yield self.assert_faults(
            d, 400, u"Source inbound-receiving endpoint"
            " {u'uuid': %r} should link"
            " to an outbound-receiving endpoint but links to {u'uuid': %r}"
            % (endpoint_uuid, endpoint_uuid))

    @inlineCallbacks
    def test_update_routing_table(self):
        conv, router, tag = yield self._setup_routing_table()
        routing_table = self.mk_routing_table([
            (('TRANSPORT_TAG:pool:tag1', 'default'),
             ('CONVERSATION:%s:%s' % (conv.conversation_type, conv.key),
              'default')),
        ])
        result = yield self.proxy.callRemote(
            "update_routing_table", self.campaign_key, routing_table)
        self.assertIdentical(result, None)

    @inlineCallbacks
    def test_conversation_action_error(self):
        campaign_key, conv_key = u"campaign-1", u"conv-1"
        d = self.proxy.callRemote(
            "conversation.unknown.bar", campaign_key, conv_key,
            {"param": 1})
        yield self.assert_faults(d, METHOD_NOT_FOUND,
                                 u"no such sub-handler unknown")

    @inlineCallbacks
    def test_router_action_error(self):
        campaign_key, router_key = u"campaign-1", u"router-1"
        d = self.proxy.callRemote(
            "router.unknown.foo", campaign_key, router_key,
            {"param": 1})
        yield self.assert_faults(d, METHOD_NOT_FOUND,
                                 u"no such sub-handler unknown")


class GoApiWorkerTestCase(AppWorkerTestCase):

    @inlineCallbacks
    def get_api_worker(self, config=None, start=True, auth=True):
        config = {} if config is None else config
        config.setdefault('worker_name', 'test_api_worker')
        config.setdefault('twisted_endpoint', 'tcp:0')
        config.setdefault('web_path', 'api')
        config.setdefault('health_path', 'health')
        config = self.mk_config(config)
        worker = yield self.get_worker(config, GoApiWorker, start)

        vumi_api = worker.vumi_api
        user, password = None, None
        if auth:
            account = yield self.mk_user(vumi_api, u"user-1")
            session_id = "session-1"
            session = {}
            vumi_api.session_manager.set_user_account_key(
                session, account.key)
            yield vumi_api.session_manager.create_session(
                session_id, session, expire_seconds=30)
            user, password = "session_id", session_id

        if not start:
            returnValue(worker)
        yield worker.startService()

        port = worker._web_service._waitingForPort.result
        addr = port.getHost()

        proxy = Proxy("http://%s:%d/api/" % (addr.host, addr.port),
                      user=user, password=password)
        returnValue((worker, proxy))

    @inlineCallbacks
    def test_invalid_auth(self):
        worker, proxy = yield self.get_api_worker(auth=False)
        try:
            yield proxy.callRemote('system.listMethods')
        except ValueError, e:
            self.assertEqual(e.args, ('401', 'Unauthorized'))
        else:
            self.fail("Expected 401 Unauthorized")

    @inlineCallbacks
    def test_valid_auth(self):
        worker, proxy = yield self.get_api_worker()
        yield proxy.callRemote('system.listMethods')
        # if we reach here the proxy call didn't throw an authentication error

    @inlineCallbacks
    def test_list_methods(self):
        worker, proxy = yield self.get_api_worker()
        result = yield proxy.callRemote('system.listMethods')
        self.assertTrue(u'conversations' in result)

    @inlineCallbacks
    def test_method_help(self):
        worker, proxy = yield self.get_api_worker()
        result = yield proxy.callRemote('system.methodHelp', 'campaigns')
        self.assertEqual(result, u"\n".join([
            "List the campaigns a user has access to.",
            "",
            ":rtype List:",
            "    List of campaigns.",
        ]))

    @inlineCallbacks
    def test_method_signature(self):
        worker, proxy = yield self.get_api_worker()
        result = yield proxy.callRemote('system.methodSignature',
                                        'campaigns')
        self.assertEqual(result, [[u'array']])

    @inlineCallbacks
    def test_health_resource(self):
        worker, proxy = yield self.get_api_worker()
        result = yield http_request(
            "http://%s:%s/health" % (proxy.host, proxy.port),
            data=None, method='GET')
        self.assertEqual(result, "OK")
