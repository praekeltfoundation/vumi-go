# -*- coding: utf-8 -*-

"""Tests for go.apps.opt_out application"""

import uuid

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage

from go.apps.opt_out.vumi_app import OptOutApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.account import AccountStore
from go.vumitools.opt_out import OptOutStore


class TestOptOutApplication(AppWorkerTestCase):

    application_class = OptOutApplication
    transport_type = u'sms'

    @inlineCallbacks
    def setUp(self):
        super(TestOptOutApplication, self).setUp()
        self.config = self.make_config({'worker_name': 'opt_out_application'})

        # Setup the OptOutApplication
        self.app = yield self.get_application(self.config)

        # Setup the command dispatcher so we cand send it commands
        self.cmd_dispatcher = yield self.get_application({
            'transport_name': 'cmd_dispatcher',
            'worker_names': ['opt_out_application'],
            }, cls=CommandDispatcher)

        # Steal app's riak manager
        self.manager = self.app.store.manager  # YOINK!
        self._persist_riak_managers.append(self.manager)

        # Create a test user account
        self.account_store = AccountStore(self.manager)
        self.user_account = yield self.account_store.new_user(u'testuser')
        self.user_api = yield VumiUserApi.from_config_async(
            self.user_account.key, self.config)

        # Add tags
        self.user_api.api.declare_tags([("pool", "tag1"), ("pool", "tag2")])
        self.user_api.api.set_pool_metadata("pool", {
            "transport_type": self.transport_type,
            "msg_options": {
                "transport_name": self.transport_name,
            },
        })

        # Give a user access to a tagpool
        self.user_api.api.account_store.tag_permissions(uuid.uuid4().hex,
            tagpool=u"pool", max_keys=None)

        self.conversation = yield self.create_conversation(u'opt_out',
            u'Subject', u'Message',
            delivery_tag_pool=u'pool',
            delivery_class=self.transport_type)
        yield self.conversation.save()

    @inlineCallbacks
    def create_conversation(self, conversation_type, subject, message, **kw):
        conversation = yield self.user_api.new_conversation(
            conversation_type, subject, message, **kw)
        yield conversation.save()
        returnValue(self.user_api.wrap_conversation(conversation))

    @inlineCallbacks
    def opt_out(self, from_addr, to_addr, content, transport_type=None,
                helper_metadata=None):
        if transport_type:
            self.transport_type = transport_type
        if helper_metadata is None:
            helper_metadata = {"go": {"user_account": "testuser"}}
        msg = TransportUserMessage(
            to_addr=to_addr,
            from_addr=from_addr,
            content=content,
            session_event=None,
            transport_name=self.transport_name,
            transport_type=self.transport_type,
            helper_metadata=helper_metadata,
            )
        yield self.dispatch(msg)

    @inlineCallbacks
    def wait_for_messages(self, nr_of_messages, total_length):
        msgs = yield self.wait_for_dispatched_messages(total_length)
        returnValue(msgs[-1 * nr_of_messages:])

    @inlineCallbacks
    def test_sms_opt_out(self):
        yield self.conversation.start()
        yield self.opt_out("12345", "666", "STOP")
        [msg] = self.get_dispatched_messages()
        self.assertEqual(msg.get('content'), "You have opted out")
        opt_out_store = OptOutStore(self.manager, "testuser")
        opt_out = yield opt_out_store.get_opt_out("msisdn", "12345")
        self.assertNotEqual(opt_out, None)

    @inlineCallbacks
    def test_sms_opt_out_no_account(self):
        yield self.conversation.start()
        yield self.opt_out("12345", "666", "STOP", helper_metadata={})
        [msg] = self.get_dispatched_messages()
        self.assertEqual(msg.get('content'),
                         "Your opt-out was received but we failed to link it "
                         "to a specific service, please try again later.")

    @inlineCallbacks
    def test_http_opt_out(self):
        yield self.conversation.start()
        yield self.opt_out("12345", "666", "STOP", "http_api")
        [msg] = yield self.wait_for_dispatched_messages(1)
        self.assertEqual(msg.get('content'),
                '{"msisdn":"12345","opted_in": false}')
        opt_out_store = OptOutStore(self.manager, "testuser")
        opt_out = yield opt_out_store.get_opt_out("msisdn", "12345")
        self.assertNotEqual(opt_out, None)
