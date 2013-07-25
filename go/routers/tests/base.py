from datetime import datetime

from django.core.urlresolvers import reverse

from vumi.message import TransportUserMessage, TransportEvent

from go.base.utils import get_router_view_definition
from go.base.tests.utils import VumiGoDjangoTestCase
from go.base import utils as base_utils


class DjangoGoRouterTestCase(VumiGoDjangoTestCase):
    use_riak = True

    TEST_ROUTER_NAME = u"Test Router"
    TEST_ROUTER_TYPE = u'keyword'

    # These are used for the mkmsg_in and mkmsg_out helper methods
    transport_name = 'sphex'
    transport_type = 'sms'

    def setUp(self):
        super(DjangoGoRouterTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def setup_router(self, config=None):
        if config is None:
            config = {}
        params = {
            'router_type': self.TEST_ROUTER_TYPE,
            'name': self.TEST_ROUTER_NAME,
            'description': u"Test router",
            'config': config,
        }
        self.router = self.create_router(**params)
        self.router_key = self.router.key

    def get_latest_router(self):
        # We won't have too many here, so doing it naively is fine.
        routers = []
        for key in self.router_store.list_routers():
            routers.append(self.router_store.get_router_by_key(key))
        return max(routers, key=lambda r: r.created_at)

    def post_new_router(self, name='router name'):
        return self.client.post(self.get_new_view_url(), {
            'name': name,
            'router_type': self.TEST_ROUTER_TYPE,
        })

    def mkmsg_ack(self, user_message_id='1', sent_message_id='abc',
                  transport_metadata=None, transport_name=None):
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportEvent(
            event_type='ack',
            user_message_id=user_message_id,
            sent_message_id=sent_message_id,
            transport_name=transport_name,
            transport_metadata=transport_metadata,
            )

    def mkmsg_nack(self, user_message_id='1', transport_metadata=None,
                    transport_name=None, nack_reason='unknown'):
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportEvent(
            event_type='nack',
            nack_reason=nack_reason,
            user_message_id=user_message_id,
            transport_name=transport_name,
            transport_metadata=transport_metadata,
            )

    def mkmsg_delivery(self, status='delivered', user_message_id='abc',
                       transport_metadata=None, transport_name=None):
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportEvent(
            event_type='delivery_report',
            transport_name=transport_name,
            user_message_id=user_message_id,
            delivery_status=status,
            to_addr='+41791234567',
            transport_metadata=transport_metadata,
            )

    def mkmsg_in(self, content='hello world', message_id='abc',
                 to_addr='9292', from_addr='+41791234567', group=None,
                 session_event=None, transport_type=None,
                 helper_metadata=None, transport_metadata=None,
                 transport_name=None):
        if transport_type is None:
            transport_type = self.transport_type
        if helper_metadata is None:
            helper_metadata = {}
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        return TransportUserMessage(
            from_addr=from_addr,
            to_addr=to_addr,
            group=group,
            message_id=message_id,
            transport_name=transport_name,
            transport_type=transport_type,
            transport_metadata=transport_metadata,
            helper_metadata=helper_metadata,
            content=content,
            session_event=session_event,
            timestamp=datetime.now(),
            )

    def mkmsg_out(self, content='hello world', message_id='1',
                  to_addr='+41791234567', from_addr='9292', group=None,
                  session_event=None, in_reply_to=None,
                  transport_type=None, transport_metadata=None,
                  transport_name=None, helper_metadata=None,
                  ):
        if transport_type is None:
            transport_type = self.transport_type
        if transport_metadata is None:
            transport_metadata = {}
        if transport_name is None:
            transport_name = self.transport_name
        if helper_metadata is None:
            helper_metadata = {}
        params = dict(
            to_addr=to_addr,
            from_addr=from_addr,
            group=group,
            message_id=message_id,
            transport_name=transport_name,
            transport_type=transport_type,
            transport_metadata=transport_metadata,
            content=content,
            session_event=session_event,
            in_reply_to=in_reply_to,
            helper_metadata=helper_metadata,
            )
        return TransportUserMessage(**params)

    def get_api_commands_sent(self):
        return base_utils.connection.get_commands()

    def get_view_url(self, view, router_key=None):
        if router_key is None:
            router_key = self.router_key
        view_def = get_router_view_definition(self.TEST_ROUTER_TYPE)
        return view_def.get_view_url(view, router_key=router_key)

    def get_new_view_url(self):
        return reverse('routers:new_router')

    def get_router(self, router_key=None):
        if router_key is None:
            router_key = self.router_key
        return self.user_api.get_router(router_key)
