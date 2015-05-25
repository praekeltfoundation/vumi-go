from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import VumiTestCase, MessageHelper
from vumi.tests.utils import LogCatcher

from go.vumitools.routing import (
    AccountRoutingTableDispatcher, RoutingMetadata,
    RoutingError, UnroutableMessageError, NoTargetError)
from go.vumitools.routing_table import RoutingTable
from go.vumitools.tests.helpers import VumiApiHelper
from go.vumitools.utils import MessageMetadataHelper


class TestRoutingMetadata(VumiTestCase):
    def mk_msg_rmeta(self, **routing_metadata):
        # We don't need a real message, just a container for routing_metadata.
        msg = {'routing_metadata': routing_metadata}
        return msg, RoutingMetadata(msg)

    def set_hops(self, msg, hops):
        msg['routing_metadata']['go_hops'] = hops

    def set_outbound_hops(self, msg, hops):
        msg['routing_metadata']['go_outbound_hops'] = hops

    def assert_hops(self, msg, hops):
        self.assertEqual(hops, msg['routing_metadata'].get('go_hops'))

    def assert_outbound_hops(self, msg, hops):
        self.assertEqual(hops, msg['routing_metadata'].get('go_outbound_hops'))

    def test_get_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_hops(msg, None)
        self.assertEqual([], rmeta.get_hops())
        self.assert_hops(msg, [])
        self.assertEqual([], rmeta.get_hops())
        self.set_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_hops(msg, [[['sc1', 'se1'], ['dc1', 'de1']]])
        self.assertEqual([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ], rmeta.get_hops())

    def test_set_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_hops(msg, None)
        rmeta.set_hops([['sc1', 'se1'], ['dc1', 'de1']])
        self.assert_hops(msg, [['sc1', 'se1'], ['dc1', 'de1']])

    def test_get_outbound_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_outbound_hops(msg, None)
        self.assertEqual(None, rmeta.get_outbound_hops())
        self.set_outbound_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_outbound_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assertEqual([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ], rmeta.get_outbound_hops())

    def test_set_outbound_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_outbound_hops(msg, None)
        rmeta.set_outbound_hops([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_outbound_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])

    def test_push_hop(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_hops(msg, None)
        rmeta.push_hop(['sc1', 'se1'], ['dc1', 'de1'])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        rmeta.push_hop(['sc2', 'se2'], ['dc2', 'de2'])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sc2', 'se2'], ['dc2', 'de2']],
        ])
        rmeta.push_hop(['sc2', 'se2'], ['dc2', 'de2'])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sc2', 'se2'], ['dc2', 'de2']],
            [['sc2', 'se2'], ['dc2', 'de2']],
        ])

    def test_push_source_no_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_hops(msg, None)
        rmeta.push_source('sconn', 'sep')
        self.assert_hops(msg, [
            [['sconn', 'sep'], None],
        ])

    def test_push_source_with_hops(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        rmeta.push_source('sconn', 'sep')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], None],
        ])

    def test_push_source_twice(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.push_source('sc1', 'se1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], None],
        ])
        self.assertRaises(RoutingError, rmeta.push_source, 'sc1', 'se1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], None],
        ])
        self.assertRaises(RoutingError, rmeta.push_source, 'sc2', 'se2')

    def test_push_destination_no_hops(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[[['sconn', 'sep'], None]])
        self.assert_hops(msg, [[['sconn', 'sep'], None]])
        rmeta.push_destination('dconn', 'dep')
        self.assert_hops(msg, [
            [['sconn', 'sep'], ['dconn', 'dep']],
        ])

    def test_push_destination_with_hops(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], None],
        ])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], None],
        ])
        rmeta.push_destination('dconn', 'dep')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], ['dconn', 'dep']],
        ])

    def test_push_destination_twice(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[[['sc1', 'se1'], None]])
        rmeta.push_destination('dc1', 'de1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assertRaises(RoutingError, rmeta.push_destination, 'dc1', 'de1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assertRaises(RoutingError, rmeta.push_destination, 'dc2', 'de2')

    def assert_next_hop(self, hops, outbound, expected):
        msg, rmeta = self.mk_msg_rmeta(go_hops=hops, go_outbound_hops=outbound)
        self.assertEqual(expected, rmeta.next_hop())

    def test_next_hop_without_hops(self):
        self.assert_next_hop(None, None, None)
        self.assert_next_hop([], [], None)
        self.assert_next_hop([1, 2, 3], [], None)
        self.assert_next_hop([1, 2, 3], [1, 2], None)

    def test_next_hop_dest_set(self):
        self.assert_next_hop([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ], [
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], None)

    def test_next_hop_first(self):
        self.assert_next_hop([
            [['sc1', 'se1'], None],
        ], [
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], ['dc1', 'de1'])

    def test_next_hop_second(self):
        self.assert_next_hop([
            [['sc1', 'se1'], ['sc1', 'de1']],
            [['sc2', 'se2'], None],
        ], [
            [['dc3', 'de3'], ['sc3', 'se3']],
            [['dc2', 'de2'], ['sc2', 'se2']],
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], ['dc2', 'de2'])

    def assert_next_router_endpoint(self, hops, outbound, expected):
        msg, rmeta = self.mk_msg_rmeta(go_hops=hops, go_outbound_hops=outbound)
        self.assertEqual(expected, rmeta.next_router_endpoint())

    def test_next_router_endpoint_without_hops(self):
        self.assert_next_router_endpoint(None, None, None)
        self.assert_next_router_endpoint([], [], None)
        self.assert_next_router_endpoint([1, 2, 3], [], None)
        self.assert_next_router_endpoint([1, 2, 3], [1, 2], None)

    def test_next_router_endpoint_first(self):
        self.assert_next_router_endpoint([], [
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], 'se1')

    def test_next_router_endpoint_second(self):
        self.assert_next_router_endpoint([
            [['sc1', 'se1'], ['sc1', 'de1']],
        ], [
            [['dc3', 'de3'], ['sc3', 'se3']],
            [['dc2', 'de2'], ['sc2', 'se2']],
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], 'se2')

    def assert_unroutable(self, msg, unroutable):
        self.assertEqual(msg['routing_metadata'].get('is_reply_to_unroutable'),
                         unroutable)

    def test_set_unroutable_reply(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_unroutable(msg, None)
        rmeta.set_unroutable_reply()
        self.assert_unroutable(msg, True)

    def test_get_unroutable_reply(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assertEqual(rmeta.get_unroutable_reply(), False)
        rmeta.set_unroutable_reply()
        self.assertEqual(rmeta.get_unroutable_reply(), True)

    def test_unroutable_event_done_not_unroutable(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assertEqual(rmeta.unroutable_event_done(), False)

    def test_unroutable_event_done_no_hops_at_all(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.set_unroutable_reply()
        self.assertEqual(rmeta.unroutable_event_done(), True)

    def test_unroutable_event_done_no_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.set_unroutable_reply()
        self.set_outbound_hops(msg, [["sc1", "se1"], ["dc1", "de1"]])
        self.assertEqual(rmeta.unroutable_event_done(), False)

    def test_unroutable_event_done_no_outbound_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.set_unroutable_reply()
        self.set_hops(msg, [["sc1", "se1"], ["dc1", "de1"]])
        self.assertEqual(rmeta.unroutable_event_done(), False)

    def test_unroutable_event_done_hops_mismatched_src(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.set_unroutable_reply()
        self.set_hops(msg, [["sc1", "dc1"], ["sc2", "dc2"]])
        self.set_outbound_hops(msg, [["dc2", "other"], ["dc1", "sc1"]])
        self.assertEqual(rmeta.unroutable_event_done(), False)

    def test_unroutable_event_done_hops_mismatched_dst(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.set_unroutable_reply()
        self.set_hops(msg, [["sc1", "dc1"], ["sc2", "dc2"]])
        self.set_outbound_hops(msg, [["other", "sc2"], ["dc1", "sc1"]])
        self.assertEqual(rmeta.unroutable_event_done(), False)

    def test_unroutable_event_done_hops_match(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.set_unroutable_reply()
        self.set_hops(msg, [["sc1", "dc1"], ["sc2", "dc2"]])
        self.set_outbound_hops(msg, [["dc2", "sc2"], ["dc1", "sc1"]])
        self.assertEqual(rmeta.unroutable_event_done(), True)


class RoutingTableDispatcherTestCase(VumiTestCase):
    """Base class for ``AccountRoutingTableDispatcher`` test cases"""

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'testuser')
        self.user_account_key = self.user_helper.account_key

        user_account = yield self.user_helper.get_user_account()
        user_account.routing_table = self.get_routing_table()
        yield user_account.save()

        tag1, tag2, tag3 = yield self.vumi_helper.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"], metadata={
                "transport_name": "sphex",
            })
        yield self.user_helper.add_tagpool_permission(u"pool1")
        yield self.user_helper.user_api.acquire_specific_tag(tag1)
        yield self.user_helper.user_api.acquire_specific_tag(tag2)
        yield self.user_helper.user_api.acquire_specific_tag(tag3)
        # We use vumi's MessageHelper here rather than our own GoMessageHelper
        # because we want to handle all the Go metadata stuff ourselves.
        self.msg_helper = self.add_helper(MessageHelper())

    def get_routing_table(self):
        return RoutingTable({
            # Transport side
            "TRANSPORT_TAG:pool1:1234": {
                "default": ["CONVERSATION:app1:conv1", "default"]},
            "TRANSPORT_TAG:pool1:5678": {
                "default": ["CONVERSATION:app1:conv1", "other"]},
            "TRANSPORT_TAG:pool1:9012": {
                "default": ["CONVERSATION:app2:conv2", "default"]},
            # Application side
            "CONVERSATION:app1:conv1": {
                "default": ["TRANSPORT_TAG:pool1:1234", "default"],
                "other": ["TRANSPORT_TAG:pool1:5678", "default"],
                "router": ["ROUTER:router:router1:OUTBOUND", "default"],
            },
            "CONVERSATION:app2:conv2": {
                "default": ["TRANSPORT_TAG:pool1:9012", "default"],
            },
            # Router outbound
            "ROUTER:router:router1:INBOUND": {
                "default": ["TRANSPORT_TAG:pool1:1234", "default"],
                "other": ["TRANSPORT_TAG:pool1:5678", "default"],
            },
            # Router inbound
            "ROUTER:router:router1:OUTBOUND": {
                "default": ["CONVERSATION:app1:conv1", "default"],
                "other": ["CONVERSATION:app2:conv2", "yet-another"],
            },
        })

    def with_md(self, msg, user_account=None, conv=None, router=None,
                endpoint=None, tag=None, hops=None, outbound_hops_from=None,
                is_paid=False, is_reply_to_unroutable=False, optout=None):
        helper_metadata = msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(self.vumi_helper.get_vumi_api(), msg)
        if user_account is not None:
            md.set_user_account(user_account)
        if conv is not None:
            conv_type, conv_key = conv
            md.set_conversation_info(conv_type, conv_key)
            md.set_user_account(self.user_account_key)
        if router is not None:
            router_type, router_key = router
            md.set_router_info(router_type, router_key)
            md.set_user_account(self.user_account_key)
        if endpoint is None:
            endpoint = msg.get_routing_endpoint()
        msg.set_routing_endpoint(endpoint)
        if tag is not None:
            md.set_tag(tag)
        if is_paid:
            md.set_paid()
        if hops is not None:
            rmeta = RoutingMetadata(msg)
            for src, dst in zip(hops[:-1], hops[1:]):
                rmeta.push_hop(src, dst)
        if outbound_hops_from is not None:
            rmeta = RoutingMetadata(msg)
            outbound_rmeta = RoutingMetadata(outbound_hops_from)
            rmeta.set_outbound_hops(outbound_rmeta.get_hops())
        if is_reply_to_unroutable:
            rmeta = RoutingMetadata(msg)
            rmeta.set_unroutable_reply()
        if optout is not None:
            helper_metadata['optout'] = optout
        return msg

    def assert_rkeys_used(self, *rkeys):
        broker = self.vumi_helper.get_worker_helper().broker
        self.assertEqual(set(rkeys), set(broker.dispatched['vumi'].keys()))

    def assert_reply_matches(self, reply, msg, content,
                             session_event='close', **md):
        expected = msg.reply(content, session_event=session_event)
        expected = self.with_md(expected, **md)

        expected["message_id"] = reply["message_id"]
        expected["timestamp"] = reply["timestamp"]
        self.assertEqual(reply, expected)

    def assert_unroutable_reply(self, connector_name, msg,
                                reply_content, **md):
        md['is_reply_to_unroutable'] = True
        self.assert_rkeys_used(
            '%s.inbound' % (connector_name,),
            '%s.outbound' % (connector_name,))

        [reply] = self.get_dispatched_outbound(connector_name)
        self.assert_reply_matches(reply, msg, reply_content, **md)

    def assert_events_equal(self, events1, events2, clear_caches=True):
        """ Assert that lists of events are equal, clearing the message
            cache of each event first if requested.
        """
        if clear_caches:
            for ev in events1 + events2:
                ev.cache.clear()
        self.assertEqual(events1, events2)

    @inlineCallbacks
    def mk_msg_reply(self, **kw):
        "Create and store an outbound message, then create a reply for it."
        msg = self.with_md(self.msg_helper.make_inbound("foo"), **kw)
        yield self.vumi_helper.get_vumi_api().mdb.add_inbound_message(msg)
        reply = msg.reply(content="Reply")
        returnValue((msg, reply))

    @inlineCallbacks
    def mk_msg_ack(self, **kw):
        "Create and store an outbound message, then create an ack for it."
        msg = self.with_md(self.msg_helper.make_outbound("foo"), **kw)
        yield self.vumi_helper.get_vumi_api().mdb.add_outbound_message(msg)
        ack = self.msg_helper.make_ack(msg)
        returnValue((msg, ack))

    def mk_unroutable_tagpool(self, name, transport_name="sphex",
                              transport_type="sms", **kw):
        metadata = {
            "reply_to_unroutable_inbound": True,
            "transport_name": transport_name,
            "transport_type": transport_type,
        }
        metadata.update(kw)
        return self.vumi_helper.get_vumi_api().tpm.set_metadata(
            name, metadata)

    def dispatch_inbound(self, msg, connector_name):
        worker_helper = self.vumi_helper.get_worker_helper(connector_name)
        return worker_helper.dispatch_inbound(msg)

    def dispatch_outbound(self, msg, connector_name):
        worker_helper = self.vumi_helper.get_worker_helper(connector_name)
        return worker_helper.dispatch_outbound(msg)

    def dispatch_event(self, msg, connector_name):
        worker_helper = self.vumi_helper.get_worker_helper(connector_name)
        return worker_helper.dispatch_event(msg)

    def get_dispatched_inbound(self, connector_name):
        worker_helper = self.vumi_helper.get_worker_helper(connector_name)
        return worker_helper.get_dispatched_inbound()

    def get_dispatched_outbound(self, connector_name):
        worker_helper = self.vumi_helper.get_worker_helper(connector_name)
        return worker_helper.get_dispatched_outbound()

    def get_dispatched_events(self, connector_name):
        worker_helper = self.vumi_helper.get_worker_helper(connector_name)
        return worker_helper.get_dispatched_events()


class TestRoutingTableDispatcher(RoutingTableDispatcherTestCase):

    def get_dispatcher(self, **extra_config):
        config = self.vumi_helper.mk_config({
            "receive_inbound_connectors": [
                "sphex", "router_ro"
            ],
            "receive_outbound_connectors": [
                "app1", "app2", "router_ri", "optout"
            ],
            "metrics_prefix": "foo",
            "application_connector_mapping": {
                "app1": "app1",
                "app2": "app2",
            },
            "router_inbound_connector_mapping": {
                "router": "router_ro",
            },
            "router_outbound_connector_mapping": {
                "router": "router_ri",
            },
            "opt_out_connector": "optout",
            "optouts": {"keywords": ["stop"]}
        })
        config.update(extra_config)
        return self.vumi_helper.get_worker_helper().get_worker(
            AccountRoutingTableDispatcher, config)

    @inlineCallbacks
    def test_inbound_message_from_transport_to_app1(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo"), tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.with_md(msg, conv=('app1', 'conv1'), optout={'optout': False},
                     hops=[
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_app2(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo"), tag=("pool1", "9012"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app2.inbound')
        self.with_md(msg, conv=('app2', 'conv2'), optout={'optout': False},
                     hops=[
                         ['TRANSPORT_TAG:pool1:9012', 'default'],
                         ['CONVERSATION:app2:conv2', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo"), tag=("pool1", "5678"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.with_md(msg, conv=('app1', 'conv1'), endpoint='other',
                     optout={'optout': False}, hops=[
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                         ['CONVERSATION:app1:conv1', 'other'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_optout(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg = self.with_md(self.msg_helper.make_inbound("stop"), tag=tag)
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'optout.inbound')
        self.with_md(msg, user_account=self.user_account_key,
                     optout={
                         'optout': True,
                         'optout_keyword': 'stop'
                     }, hops=[
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                         ['OPT_OUT', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('optout'))

    @inlineCallbacks
    def test_inbound_message_from_router(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo"),
            optout={'optout': False},
            router=('router', 'router1'))
        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app1.inbound')
        self.with_md(msg, conv=("app1", "conv1"),
                     hops=[
                         ['ROUTER:router:router1:OUTBOUND', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_router_to_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"),
            optout={'optout': False},
            router=('router', 'router1'),
            endpoint='other')
        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app2.inbound')
        self.with_md(msg, conv=("app2", "conv2"), endpoint='yet-another',
                     hops=[
                         ['ROUTER:router:router1:OUTBOUND', 'other'],
                         ['CONVERSATION:app2:conv2', 'yet-another'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_inbound_message_with_no_tag_or_account(self):
        yield self.get_dispatcher()
        msg = self.msg_helper.make_inbound("foo")
        with LogCatcher() as lc:
            yield self.dispatch_inbound(msg, 'sphex')
            [err] = lc.errors
        self.assert_rkeys_used('sphex.inbound')
        [failure] = self.flushLoggedErrors(UnroutableMessageError)
        self.assertEqual(err['failure'], failure)
        self.assertEqual(err['why'], 'Error routing message for sphex')
        self.assertEqual(
            'No user account key or tag on message', failure.value.args[0])

    @inlineCallbacks
    def test_outbound_message_from_optout_to_transport(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg, reply = yield self.mk_msg_reply(tag=tag)
        yield self.dispatch_outbound(reply, 'optout')
        self.assert_rkeys_used('optout.outbound', 'sphex.outbound')
        self.with_md(reply, tag=tag, user_account=self.user_account_key,
                     hops=[
                         ['OPT_OUT', 'default'],
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                     ])
        self.assertEqual([reply], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_in_app1(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'))
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"),
                     hops=[
                         ['CONVERSATION:app1:conv1', 'default'],
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_in_app2(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app2', 'conv2'))
        yield self.dispatch_outbound(msg, 'app2')
        self.assert_rkeys_used('app2.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "9012"),
                     hops=[
                         ['CONVERSATION:app2:conv2', 'default'],
                         ['TRANSPORT_TAG:pool1:9012', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_via_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'),
            endpoint='other')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=[
                         ['CONVERSATION:app1:conv1', 'other'],
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), router=('router', 'router1'))
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used('router_ri.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"),
                     hops=[
                         ['ROUTER:router:router1:INBOUND', 'default'],
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router_via_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), router=('router', 'router1'),
            endpoint='other')
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used('router_ri.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=[
                         ['ROUTER:router:router1:INBOUND', 'other'],
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_with_no_target(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), router=('router', 'router1'),
            endpoint='not-routed')
        with LogCatcher() as lc:
            yield self.dispatch_outbound(msg, 'router_ri')
            [err] = lc.errors
        self.assert_rkeys_used('router_ri.outbound')
        [failure] = self.flushLoggedErrors(NoTargetError)
        self.assertEqual(err['failure'], failure)
        self.assertEqual(err['why'], 'Error routing message for router_ri')
        self.assertTrue(failure.value.args[0].startswith(
            'No target found for outbound message from \'router_ri\':'
            ' <Message payload='))

    @inlineCallbacks
    def test_event_routing_to_app1(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '1234'), user_account=self.user_account_key,
            hops=[
                ['CONVERSATION:app1:conv1', 'default'],
                ['TRANSPORT_TAG:pool1:1234', 'default'],
            ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.with_md(ack, tag=('pool1', '1234'), conv=('app1', 'conv1'),
                     hops=[
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ], outbound_hops_from=msg)
        self.assert_events_equal([ack], self.get_dispatched_events('app1'))

    @inlineCallbacks
    def test_event_routing_to_app2(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '9012'), user_account=self.user_account_key,
            hops=[
                ['CONVERSATION:app2:conv2', 'default'],
                ['TRANSPORT_TAG:pool1:9012', 'default'],
            ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app2.event')
        self.with_md(ack, tag=('pool1', '9012'), conv=('app2', 'conv2'),
                     hops=[
                         ['TRANSPORT_TAG:pool1:9012', 'default'],
                         ['CONVERSATION:app2:conv2', 'default'],
                     ], outbound_hops_from=msg)
        self.assert_events_equal([ack], self.get_dispatched_events('app2'))

    @inlineCallbacks
    def test_event_routing_via_custom_endpoint(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            endpoint='other', tag=('pool1', '5678'),
            user_account=self.user_account_key,
            hops=[
                ['CONVERSATION:app1:conv1', 'other'],
                ['TRANSPORT_TAG:pool1:5678', 'default'],
            ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.with_md(ack, tag=('pool1', '5678'), conv=('app1', 'conv1'),
                     endpoint='other',
                     hops=[
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                         ['CONVERSATION:app1:conv1', 'other']
                     ], outbound_hops_from=msg)
        self.assert_events_equal([ack], self.get_dispatched_events('app1'))

    @inlineCallbacks
    def test_event_whose_outbound_has_hops_but_no_user_account(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            endpoint='other', tag=('pool1', '5678'),
            hops=[
                ['CONVERSATION:app1:conv1', 'other'],
                ['TRANSPORT_TAG:pool1:5678', 'default'],
            ])
        with LogCatcher() as lc:
            yield self.dispatch_event(ack, 'sphex')
            [err] = lc.errors
        self.assert_rkeys_used('sphex.event')
        [failure] = self.flushLoggedErrors(UnroutableMessageError)
        self.assertEqual(err['failure'], failure)
        self.assertEqual(err['why'], 'Error routing message for sphex')
        self.assertTrue(failure.value.args[0].startswith(
            'Outbound message for event has no associated user account:'
            ' <Message payload='))

    @inlineCallbacks
    def test_outbound_message_gets_transport_fields(self):
        yield self.get_dispatcher()
        yield self.vumi_helper.get_vumi_api().tpm.set_metadata("pool1", {
            'transport_name': 'sphex',
            'transport_type': 'sms',
        })
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'))
        msg['transport_name'] = None
        msg['transport_type'] = None
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        msg['transport_name'] = 'sphex'
        msg['transport_type'] = 'sms'
        self.with_md(msg, tag=("pool1", "1234"), hops=[
            ['CONVERSATION:app1:conv1', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default'],
        ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_gets_stored_before_transport(self):
        """
        Outbound messages going to transports are stored.
        """
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'))

        mdb = self.vumi_helper.get_vumi_api().mdb
        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"), hops=[
            ['CONVERSATION:app1:conv1', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default'],
        ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, msg)

    @inlineCallbacks
    def test_outbound_message_does_not_get_stored_if_disabled(self):
        """
        Outbound messages going to transports are not stored when storing is
        disabled.
        """
        yield self.get_dispatcher(store_messages_to_transports=False)
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'))

        mdb = self.vumi_helper.get_vumi_api().mdb
        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"), hops=[
            ['CONVERSATION:app1:conv1', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default'],
        ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

    @inlineCallbacks
    def test_outbound_message_does_not_get_stored_before_router(self):
        """
        Outbound messages going to routers are not stored.
        """
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'),
            endpoint="router")

        mdb = self.vumi_helper.get_vumi_api().mdb
        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'router_ro.outbound')
        self.with_md(
            msg, router=("router", "router1"), endpoint="default", hops=[
                ['CONVERSATION:app1:conv1', 'router'],
                ['ROUTER:router:router1:OUTBOUND', 'default'],
            ])
        self.assertEqual([msg], self.get_dispatched_outbound('router_ro'))

        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)


class TestRoutingTableDispatcherWithBilling(RoutingTableDispatcherTestCase):

    def get_dispatcher(self, **extra_config):
        config = self.vumi_helper.mk_config({
            "receive_inbound_connectors": [
                "sphex", "router_ro", "billing_dispatcher_ro"
            ],
            "receive_outbound_connectors": [
                "app1", "app2", "router_ri", "optout",
                "billing_dispatcher_ri"
            ],
            "billing_inbound_connector": "billing_dispatcher_ri",
            "billing_outbound_connector": "billing_dispatcher_ro",
            "metrics_prefix": "foo",
            "application_connector_mapping": {
                "app1": "app1",
                "app2": "app2",
            },
            "router_inbound_connector_mapping": {
                "router": "router_ro",
            },
            "router_outbound_connector_mapping": {
                "router": "router_ri",
            },
            "opt_out_connector": "optout",
            "default_unroutable_inbound_reply": "Eep!",
            "optouts": {"keywords": ["stop"]}
        })
        config.update(extra_config)
        return self.vumi_helper.get_worker_helper().get_worker(
            AccountRoutingTableDispatcher, config)

    @inlineCallbacks
    def test_inbound_message_from_transport_to_billing(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo"), tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used(
            'sphex.inbound', 'billing_dispatcher_ri.inbound')

        hops = [
            ['TRANSPORT_TAG:pool1:1234', 'default'],
            ['BILLING:INBOUND', 'default']
        ]
        self.with_md(msg, user_account=self.user_account_key,
                     hops=hops, optout={'optout': False})
        self.assertEqual(
            [msg], self.get_dispatched_inbound('billing_dispatcher_ri'))

    @inlineCallbacks
    def test_inbound_message_from_billing_to_app1(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo"),
            user_account=self.user_account_key,
            optout={'optout': False},
            tag=("pool1", "1234"), hops=[
                ['TRANSPORT_TAG:pool1:1234', 'default'],
                ['BILLING:INBOUND', 'default']
            ])

        yield self.dispatch_inbound(msg, 'billing_dispatcher_ro')
        self.assert_rkeys_used(
            'billing_dispatcher_ro.inbound', 'app1.inbound')

        self.with_md(msg, conv=('app1', 'conv1'),
                     hops=[
                         ['BILLING:OUTBOUND', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ])
        self.assertEqual(
            [msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_optout_message_from_transport_to_billing(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("stop"), tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used(
            'sphex.inbound', 'billing_dispatcher_ri.inbound')
        hops = [
            ['TRANSPORT_TAG:pool1:1234', 'default'],
            ['BILLING:INBOUND', 'default'],
        ]
        self.with_md(msg, user_account=self.user_account_key, hops=hops,
                     optout={
                         'optout': True,
                         'optout_keyword': 'stop'
                     })
        self.assertEqual(
            [msg], self.get_dispatched_inbound('billing_dispatcher_ri'))

    @inlineCallbacks
    def test_inbound_message_from_billing_to_optout(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("stop"),
            tag=("pool1", "1234"),
            optout={'optout': True})
        yield self.dispatch_inbound(msg, 'billing_dispatcher_ro')
        self.assert_rkeys_used(
            'billing_dispatcher_ro.inbound', 'optout.inbound')

        hops = [
            ['BILLING:OUTBOUND', 'default'],
            ['OPT_OUT', 'default'],
        ]
        self.with_md(msg, user_account=self.user_account_key, hops=hops)
        self.assertEqual([msg], self.get_dispatched_inbound('optout'))

    @inlineCallbacks
    def test_inbound_message_from_router(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), router=('router', 'router1'),
            is_paid=True, optout={'optout': False})

        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app1.inbound')
        hops = [
            ['ROUTER:router:router1:OUTBOUND', 'default'],
            ['CONVERSATION:app1:conv1', 'default'],
        ]
        self.with_md(msg, conv=("app1", "conv1"), hops=hops)
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_outbound_message_from_optout_to_billing(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg, reply = yield self.mk_msg_reply(tag=tag)
        yield self.dispatch_outbound(reply, 'optout')
        self.assert_rkeys_used(
            'optout.outbound', 'billing_dispatcher_ro.outbound')

        hops = [
            ['OPT_OUT', 'default'],
            ['BILLING:OUTBOUND', 'default'],
        ]
        self.with_md(reply, tag=tag, user_account=self.user_account_key,
                     hops=hops)

        self.assertEqual(
            [reply], self.get_dispatched_outbound('billing_dispatcher_ro'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_in_app1_to_billing(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'))
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used(
            'app1.outbound', 'billing_dispatcher_ro.outbound')

        hops = [
            ['CONVERSATION:app1:conv1', 'default'],
            ['BILLING:OUTBOUND', 'default'],
        ]
        self.with_md(msg, tag=("pool1", "1234"), hops=hops)
        self.assertEqual(
            [msg], self.get_dispatched_outbound('billing_dispatcher_ro'))

    @inlineCallbacks
    def test_outbound_message_from_billing_to_transport(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), tag=("pool1", "1234"),
            conv=('app1', 'conv1'), is_paid=True)

        yield self.dispatch_outbound(msg, 'billing_dispatcher_ri')
        self.assert_rkeys_used(
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['BILLING:INBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default']
        ]
        self.with_md(msg, hops=hops)
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router_to_billing(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), router=('router', 'router1'))
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used(
            'router_ri.outbound', 'billing_dispatcher_ro.outbound')

        hops = [
            ['ROUTER:router:router1:INBOUND', 'default'],
            ['BILLING:OUTBOUND', 'default']
        ]
        self.with_md(msg, tag=("pool1", "1234"), hops=hops)
        self.assertEqual(
            [msg], self.get_dispatched_outbound('billing_dispatcher_ro'))

    @inlineCallbacks
    def test_router_outbound_message_from_billing_to_transport(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), tag=("pool1", "1234"),
            router=('router', 'router1'), is_paid=True)

        yield self.dispatch_outbound(msg, 'billing_dispatcher_ri')
        self.assert_rkeys_used(
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['BILLING:INBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default'],
        ]
        self.with_md(msg, hops=hops)
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_event_routing_to_app1(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '1234'), user_account=self.user_account_key,
            hops=[
                ['CONVERSATION:app1:conv1', 'default'],
                ['TRANSPORT_TAG:pool1:1234', 'default'],
            ])

        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.with_md(ack, tag=('pool1', '1234'), conv=('app1', 'conv1'),
                     hops=[
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ], outbound_hops_from=msg)

        self.assert_events_equal([ack], self.get_dispatched_events('app1'))

    @inlineCallbacks
    def test_unroutable_inbound_reply_via_billing(self):
        yield self.mk_unroutable_tagpool(u"pool1")
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            tag=("pool1", "unowned-tag"))
        yield self.dispatch_inbound(msg, 'billing_dispatcher_ro')
        self.assert_unroutable_reply(
            'billing_dispatcher_ro', msg, "Eep!", tag=("pool1", "unowned-tag"))

    @inlineCallbacks
    def test_outbound_message_gets_stored_before_transport(self):
        """
        Outbound messages going to transports are stored.
        """
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), tag=("pool1", "1234"),
            conv=('app1', 'conv1'), is_paid=True)

        mdb = self.vumi_helper.get_vumi_api().mdb
        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

        yield self.dispatch_outbound(msg, 'billing_dispatcher_ri')
        self.assert_rkeys_used(
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['BILLING:INBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default']
        ]
        self.with_md(msg, hops=hops)
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, msg)

    @inlineCallbacks
    def test_outbound_message_does_not_get_stored_if_disabled(self):
        """
        Outbound messages going to transports are not stored when storing is
        disabled.
        """
        yield self.get_dispatcher(store_messages_to_transports=False)
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), tag=("pool1", "1234"),
            conv=('app1', 'conv1'), is_paid=True)

        mdb = self.vumi_helper.get_vumi_api().mdb
        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

        yield self.dispatch_outbound(msg, 'billing_dispatcher_ri')
        self.assert_rkeys_used(
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['BILLING:INBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default']
        ]
        self.with_md(msg, hops=hops)
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

    @inlineCallbacks
    def test_outbound_message_does_not_get_stored_before_billing(self):
        """
        Outbound messages going to billing are not stored.
        """
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_outbound("foo"), conv=('app1', 'conv1'))

        mdb = self.vumi_helper.get_vumi_api().mdb
        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)

        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used(
            'app1.outbound', 'billing_dispatcher_ro.outbound')

        hops = [
            ['CONVERSATION:app1:conv1', 'default'],
            ['BILLING:OUTBOUND', 'default'],
        ]
        self.with_md(msg, tag=("pool1", "1234"), hops=hops)
        self.assertEqual(
            [msg], self.get_dispatched_outbound('billing_dispatcher_ro'))

        stored_msg = yield mdb.get_outbound_message(msg["message_id"])
        self.assertEqual(stored_msg, None)


class TestUnroutableSessionResponse(RoutingTableDispatcherTestCase):

    def get_routing_table(self):
        return RoutingTable({})

    def get_dispatcher(self):
        config = self.vumi_helper.mk_config({
            "receive_inbound_connectors": [
                "sphex", "router_ro",
            ],
            "receive_outbound_connectors": [
                "app1", "router_ri",
            ],
            "metrics_prefix": "foo",
            "application_connector_mapping": {
                "app1": "app1",
            },
            "router_inbound_connector_mapping": {
                "router": "router_ro",
            },
            "router_outbound_connector_mapping": {
                "router": "router_ri",
            },
            "opt_out_connector": "optout",
            "default_unroutable_inbound_reply": "Eep!",
        })
        return self.vumi_helper.get_worker_helper().get_worker(
            AccountRoutingTableDispatcher, config)

    @inlineCallbacks
    def test_unroutable_inbound_from_transport_to_unknown_pool(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            tag=("badpool", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound')
        [failure] = self.flushLoggedErrors()
        self.assertEqual(
            'Message received for unowned tag.', failure.value.args[0])

    @inlineCallbacks
    def test_unroutable_inbound_from_transport_no_config(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound')
        [failure] = self.flushLoggedErrors()
        self.assertEqual(
            "No target found for inbound message from 'sphex'",
            failure.value.args[0])

    @inlineCallbacks
    def test_unroutable_inbound_from_transport_no_reply(self):
        yield self.vumi_helper.get_vumi_api().tpm.set_metadata(u"pool1", {
            "reply_to_unroutable_inbound": False,
        })
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound')
        [failure] = self.flushLoggedErrors()
        self.assertEqual(
            "No target found for inbound message from 'sphex'",
            failure.value.args[0])

    @inlineCallbacks
    def test_unroutable_inbound_from_transport_default_reply(self):
        yield self.mk_unroutable_tagpool(u"pool1")
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_unroutable_reply(
            'sphex', msg, "Eep!", tag=("pool1", "1234"),
            user_account=self.user_helper.account_key,
            optout={'optout': False})

    @inlineCallbacks
    def test_unroutable_inbound_from_transport_default_reply_no_session(self):
        yield self.mk_unroutable_tagpool(u"pool1")
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo"), tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_unroutable_reply(
            'sphex', msg, "Eep!", tag=("pool1", "1234"),
            user_account=self.user_helper.account_key,
            optout={'optout': False})

    @inlineCallbacks
    def test_unroutable_inbound_from_transport_custom_reply(self):
        yield self.mk_unroutable_tagpool(
            u"pool1", unroutable_inbound_reply="Custom Eep!")
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_unroutable_reply(
            'sphex', msg, "Custom Eep!", tag=("pool1", "1234"),
            user_account=self.user_helper.account_key,
            optout={'optout': False})

    @inlineCallbacks
    def test_unroutable_inbound_from_router_no_config(self):
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            router=('router', 'badrouter'))
        yield self.dispatch_inbound(msg, 'router_ro')
        [failure] = self.flushLoggedErrors()
        self.assertEqual(
            "No target found for inbound message from 'router_ro'",
            failure.value.args[0])

    @inlineCallbacks
    def test_unroutable_inbound_from_router_default_reply(self):
        yield self.mk_unroutable_tagpool(u"pool1")
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            optout={'optout': False}, tag=("pool1", "1234"),
            router=('router', 'badrouter'))
        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_unroutable_reply(
            'router_ro', msg, "Eep!", router=("router", "badrouter"))

    @inlineCallbacks
    def test_event_for_unroutable_inbound_reply_on_unowned_tag(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '1234'), is_reply_to_unroutable=True)
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event')
        [orig_ack] = self.get_dispatched_events('sphex')
        self.assertEqual(ack, orig_ack)

    @inlineCallbacks
    def test_event_for_unroutable_inbound_reply_on_first_hop(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '1234'), is_reply_to_unroutable=True,
            user_account=self.user_account_key,
            hops=[
                ['ROUTER:router:router1:INBOUND', 'other'],
                ['TRANSPORT_TAG:pool1:1234', 'default'],
            ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'router_ri.event')
        [event] = self.get_dispatched_events('router_ri')
        expected = self.with_md(
            ack, outbound_hops_from=msg, is_reply_to_unroutable=True,
            router=("router", "router1"), user_account="user-1",
            tag=('pool1', '1234'), endpoint='other',
            hops=[
                ['TRANSPORT_TAG:pool1:1234', 'default'],
                ['ROUTER:router:router1:INBOUND', 'other'],
            ])
        self.assert_events_equal([expected], [event])

    @inlineCallbacks
    def test_event_for_unroutable_inbound_reply_on_last_hop(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '1234'), is_reply_to_unroutable=True,
            user_account=self.user_account_key, hops=[
                ['ROUTER:router:router1:INBOUND', 'other'],
                ['TRANSPORT_TAG:pool1:1234', 'default'],
            ])
        ack = self.with_md(ack, outbound_hops_from=msg, hops=[
            ['TRANSPORT_TAG:pool1:1234', 'default'],
            ['ROUTER:router:router1:INBOUND', 'other'],
        ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event')
        [orig_ack] = self.get_dispatched_events('sphex')
        self.assertEqual(ack, orig_ack)

    @inlineCallbacks
    def test_reply_for_unroutable_inbound_gets_stored(self):
        """
        Replies to unroutable messages are stored.
        """
        yield self.mk_unroutable_tagpool(u"pool1")
        yield self.get_dispatcher()
        msg = self.with_md(
            self.msg_helper.make_inbound("foo", session_event='new'),
            tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_unroutable_reply(
            'sphex', msg, "Eep!", tag=("pool1", "1234"),
            user_account=self.user_helper.account_key,
            optout={'optout': False})

        [reply] = self.get_dispatched_outbound('sphex')
        mdb = self.vumi_helper.get_vumi_api().mdb
        stored_msg = yield mdb.get_outbound_message(reply["message_id"])
        self.assertEqual(stored_msg, reply)
