from vumi.tests.helpers import MessageHelper

from go.vumitools.utils import MessageMetadataHelper


class GoMessageHelper(object):
    def __init__(self, mdb=None, **kw):
        self._msg_helper = MessageHelper(**kw)
        self.mdb = mdb

    def add_router_metadata(self, msg, router):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(None, msg)
        md.set_router_info(router.router_type, router.key)
        md.set_user_account(router.user_account.key)

    def add_conversation_metadata(self, msg, conv):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(None, msg)
        md.set_conversation_info(conv.conversation_type, conv.key)
        md.set_user_account(conv.user_account.key)

    def _add_go_metadata(self, msg, conv, router):
        if conv is not None:
            self.add_conversation_metadata(msg, conv)
        if router is not None:
            self.add_router_metadata(msg, router)

    def make_inbound(self, content, conv=None, router=None, **kw):
        msg = self._msg_helper.make_inbound(content, **kw)
        self._add_go_metadata(msg, conv, router)
        return msg

    def make_outbound(self, content, conv=None, router=None, **kw):
        msg = self._msg_helper.make_outbound(content, **kw)
        self._add_go_metadata(msg, conv, router)
        return msg

    def make_ack(self, msg=None, conv=None, router=None, **kw):
        ack = self._msg_helper.make_ack(msg, **kw)
        self._add_go_metadata(ack, conv, router)
        return ack

    def make_nack(self, msg=None, conv=None, router=None, **kw):
        nack = self._msg_helper.make_nack(msg, **kw)
        self._add_go_metadata(nack, conv, router)
        return nack

    def make_delivery_report(self, msg=None, conv=None, router=None, **kw):
        dr = self._msg_helper.make_delivery_report(msg, **kw)
        self._add_go_metadata(dr, conv, router)
        return dr

    def store_inbound(self, conv, msg):
        if self.mdb is None:
            raise ValueError("No message store provided.")
        return self.mdb.add_inbound_message(msg, batch_id=conv.batch.key)

    def store_outbound(self, conv, msg):
        if self.mdb is None:
            raise ValueError("No message store provided.")
        return self.mdb.add_outbound_message(msg, batch_id=conv.batch.key)

    def make_stored_inbound(self, conv, content, **kw):
        msg = self.make_inbound(content, conv=conv, **kw)
        d = self.store_inbound(conv, msg)
        return d.addCallback(lambda _: msg)

    def make_stored_outbound(self, conv, content, **kw):
        msg = self.make_outbound(content, conv=conv, **kw)
        d = self.store_outbound(conv, msg)
        return d.addCallback(lambda _: msg)
