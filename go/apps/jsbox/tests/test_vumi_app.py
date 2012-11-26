# -*- coding: utf-8 -*-
import pkg_resources

from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.tests.utils import AppWorkerTestCase

from go.apps.jsbox.vumi_app import JsBoxApplication

from vumi.middleware.tagger import TaggingMiddleware


class JsBoxApplicationTestCase(AppWorkerTestCase):

    use_riak = True
    application_class = JsBoxApplication

    @inlineCallbacks
    def setUp(self):
        yield super(JsBoxApplicationTestCase, self).setUp()
        node_js = '/usr/bin/nodejs'
        sandboxer_js = pkg_resources.resource_filename('vumi.application',
                                                       'sandboxer.js')
        self.config = self.mk_config({
            'executable': node_js,
            'args': [sandboxer_js],
            'timeout': 10,
        })
        self.app = yield self.get_application(self.config)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!
        self.message_store = self.vumi_api.mdb

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)

        yield self.user_api.api.declare_tags([("pool", "tag1"),
                                              ("pool", "tag2")])
        yield self.user_api.api.set_pool_metadata("pool", {
            "transport_type": "sphex",
            })

    @inlineCallbacks
    def setup_conversation(self, contact_count=2,
                           from_addr=u'+27831234567{0}',
                           metadata=None):
        user_api = self.user_api
        group = yield user_api.contact_store.new_group(u'test group')

        for i in range(contact_count):
            yield user_api.contact_store.new_contact(
                name=u'First', surname=u'Surname %s' % (i,),
                msisdn=from_addr.format(i), groups=[group])

        conversation = yield self.create_conversation(
            delivery_tag_pool=u'pool', delivery_class=u'sms',
            delivery_tag=u'tag1', metadata=metadata)
        conversation.add_group(group)
        yield conversation.save()
        returnValue(conversation)

    def set_conversation_tag(self, msg, conversation):
        # TOOD: Move into AppWorkerTestCase once it's working
        tag = (conversation.delivery_tag_pool, conversation.delivery_tag)
        TaggingMiddleware.add_tag_to_msg(msg, tag)
        return msg

    def mk_metadata(self, method):
        app_js = """
            api.%(method)s = function(command) {
                this.log_info("From command: inbound-message",
                    function (reply) {
                        this.log_info("Log successful: " + reply.success);
                        this.done();
                    }
                );
            }
        """ % {'method': method}
        metadata = {
            'jsbox': {
                'javascript': app_js,
            },
        }
        return metadata

    @inlineCallbacks
    def test_start(self):
        conversation = yield self.setup_conversation()
        yield self.start_conversation(conversation)

        # Force processing of messages
        yield self._amqp.kick_delivery()

    @inlineCallbacks
    def test_user_message(self):
        conversation = yield self.setup_conversation(
            metadata=self.mk_metadata('on_inbound_message'))
        yield self.start_conversation(conversation)
        msg = self.set_conversation_tag(self.mkmsg_in(), conversation)
        yield self.dispatch_inbound(msg)

    @inlineCallbacks
    def test_event(self):
        conversation = yield self.setup_conversation(
            metadata=self.mk_metadata('on_inbound_event'))
        yield self.start_conversation(conversation)
        msg = self.set_conversation_tag(self.mkmsg_in(), conversation)
        tag = (conversation.delivery_tag_pool, conversation.delivery_tag)
        yield self.vumi_api.mdb.add_outbound_message(msg, tag=tag)
        event = self.mkmsg_ack(user_message_id=msg['message_id'])
        yield self.dispatch_event(event)
