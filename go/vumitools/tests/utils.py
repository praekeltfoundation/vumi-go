# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

from twisted.internet.defer import inlineCallbacks

from vumi.persist.fields import (
    ForeignKeyProxy, ManyToManyProxy, DynamicProxy, ListProxy)
from vumi.tests.helpers import VumiTestCase

from go.vumitools.account import UserAccount
from go.vumitools.contact import Contact, ContactGroup
from go.vumitools.utils import MessageMetadataHelper


def field_eq(f1, f2):
    if f1 == f2:
        return True
    if isinstance(f1, ManyToManyProxy) and isinstance(f2, ManyToManyProxy):
        return f1.keys() == f2.keys()
    if isinstance(f1, ForeignKeyProxy) and isinstance(f2, ForeignKeyProxy):
        return f1.key == f2.key
    if isinstance(f1, DynamicProxy) and isinstance(f2, DynamicProxy):
        return f1.items() == f2.items()
    if isinstance(f1, ListProxy) and isinstance(f2, ListProxy):
        return list(f1) == list(f2)
    return False


def model_eq(m1, m2):
    fields = m1.field_descriptors.keys()
    if fields != m2.field_descriptors.keys():
        return False
    if m1.key != m2.key:
        return False
    for field in fields:
        if not field_eq(getattr(m1, field), getattr(m2, field)):
            return False
    return True


class FakeAmqpConnection(object):
    def __init__(self, amqp_client):
        self._amqp = amqp_client
        self._connected = False
        self.commands = []

    def is_connected(self):
        return self._connected

    def connect(self, dsn=None):
        self._connected = True

    def publish_command_message(self, command):
        # This both sends messages via self._amqp and appends them to
        # self.commands to support to different use cases -- namely,
        # testing that messages are succesfully routed and testing that
        # the correct commands are queue for sending.
        self.commands.append(command)
        return self._amqp.publish_raw('vumi', 'vumi.api', command.to_json())

    def get_commands(self):
        commands, self.commands = self.commands, []
        return commands


# class GoPersistenceMixin(PersistenceMixin):
#     # def _persist_setUp(self):
#     #     self._users_created = 0
#     #     return super(GoPersistenceMixin, self)._persist_setUp()

#     @PersistenceMixin.sync_or_async
#     def _clear_bucket_properties(self, account_keys, manager):
#         # TODO: Fix this hackery when we can.
#         import sys
#         manager_module = sys.modules[manager.__module__]
#         del_bp = getattr(manager_module, 'delete_bucket_properties', None)
#         if del_bp is None:
#             # This doesn't exist everywhere yet.
#             return

#         client = manager.client
#         for account_key in account_keys:
#             sub_manager = manager.sub_manager(account_key)
#             yield del_bp(client.bucket(sub_manager.bucket_name(Contact)))
#             yield del_bp(client.bucket(sub_manager.bucket_name(ContactGroup)))

#     def _list_accounts(self, manager):
#         bucket = manager.client.bucket(
#             manager.bucket_name(UserAccount))
#         if self.sync_persistence:
#             return bucket.get_keys()
#         return bucket.list_keys()

#     @PersistenceMixin.sync_or_async
#     def _persist_purge_riak(self, manager):
#         # If buckets are empty, they aren't listed. However, they may still
#         # have properties set. Therefore, we find all account keys and
#         # clear properties from their associated buckets.
#         accounts = yield self._list_accounts(manager)
#         yield manager.purge_all()
#         # This must happen after the objects are deleted, otherwise the
#         # indexes don't go away.
#         yield self._clear_bucket_properties(accounts, manager)


# class GoRouterWorkerTestMixin(GoPersistenceMixin):

#     def _worker_name(self):
#         # DummyApplicationWorker has no worker_name attr.
#         return getattr(self.router_class, 'worker_name', 'unnamed')

#     def _router_type(self):
#         # This is a guess based on worker_name.
#         # We need a better way to do this.
#         return self._worker_name().rpartition('_')[0].decode('utf-8')

#     def setup_router(self, config, started=True, **kw):
#         if started:
#             kw['status'] = u'running'
#         return self.create_router(config=config, **kw)

#     def create_router(self, **kw):
#         router_type = kw.pop('router_type', None)
#         if router_type is None:
#             router_type = self._router_type()
#         name = kw.pop('name', u'Subject')
#         description = kw.pop('description', u'')
#         config = kw.pop('config', {})
#         self.assertTrue(isinstance(config, dict))
#         return self.user_api.new_router(
#             router_type, name, description, config, **kw)

#     @inlineCallbacks
#     def start_router(self, router):
#         router_api = self.user_api.get_router_api(
#             router.router_type, router.key)
#         yield router_api.start_router(router)
#         for cmd in self.get_dispatcher_commands():
#             yield self.dispatch_command(
#                 cmd.payload['command'], *cmd.payload['args'],
#                 **cmd.payload['kwargs'])

#     @inlineCallbacks
#     def stop_router(self, router):
#         router_api = self.user_api.get_router_api(
#             router.router_type, router.key)
#         yield router_api.stop_router(router)
#         for cmd in self.get_dispatcher_commands():
#             yield self.dispatch_command(
#                 cmd.payload['command'], *cmd.payload['args'],
#                 **cmd.payload['kwargs'])

#     def add_router_md_to_msg(self, msg, router, endpoint=None):
#         msg.payload.setdefault('helper_metadata', {})
#         md = MessageMetadataHelper(self.vumi_api, msg)
#         md.set_router_info(router.router_type, router.key)
#         md.set_user_account(self.user_account_key)
#         if endpoint is not None:
#             msg.set_routing_endpoint(endpoint)

#     def dispatch_inbound_to_router(self, msg, router, endpoint=None):
#         self.add_router_md_to_msg(msg, router, endpoint)
#         return self.dispatch_inbound(msg, 'ri_conn')

#     def dispatch_outbound_to_router(self, msg, router, endpoint=None):
#         self.add_router_md_to_msg(msg, router, endpoint)
#         return self.dispatch_outbound(msg, 'ro_conn')

#     def dispatch_event_to_router(self, msg, router, endpoint=None):
#         self.add_router_md_to_msg(msg, router, endpoint)
#         return self.dispatch_event(msg, 'ri_conn')


# class RouterWorkerTestCase(GoRouterWorkerTestMixin, VumiWorkerTestCase):

#     use_riak = True

#     def setUp(self):
#         self._persist_setUp()
#         super(RouterWorkerTestCase, self).setUp()

#     @inlineCallbacks
#     def tearDown(self):
#         yield super(RouterWorkerTestCase, self).tearDown()
#         yield self._persist_tearDown()

#     def get_router_worker(self, config, start=True):
#         if 'worker_name' not in config:
#             config['worker_name'] = self._worker_name()
#         if 'ri_connector_name' not in config:
#             config['ri_connector_name'] = 'ri_conn'
#         if 'ro_connector_name' not in config:
#             config['ro_connector_name'] = 'ro_conn'
#         return self.get_worker(
#             config, self.router_class, start=start)
