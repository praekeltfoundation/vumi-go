# -*- test-case-name: go.vumitools.router.tests.test_models -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, ForeignKey, Timestamp, Json, ListOf
from vumi.components.message_store import Batch

from go.vumitools.account import UserAccount, PerAccountStore
from go.vumitools.routing_table import GoConnector


ROUTER_ACTIVE = u'active'
ROUTER_ARCHIVED = u'archived'

ROUTER_STARTING = u'starting'
ROUTER_RUNNING = u'running'
ROUTER_STOPPING = u'stopping'
ROUTER_STOPPED = u'stopped'


class Router(Model):
    """A router for sending messages to interesting places."""

    VERSION = 1
    MIGRATOR = None

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    description = Unicode(default=u'')
    router_type = Unicode(index=True)
    config = Json(default=dict)
    extra_inbound_endpoints = ListOf(Unicode())
    extra_outbound_endpoints = ListOf(Unicode())

    created_at = Timestamp(default=datetime.utcnow, index=True)
    archived_at = Timestamp(null=True, index=True)

    archive_status = Unicode(default=ROUTER_ACTIVE, index=True)
    status = Unicode(default=ROUTER_STOPPED, index=True)

    batch = ForeignKey(Batch)

    def active(self):
        return self.archive_status == ROUTER_ACTIVE

    def archived(self):
        return self.archive_status == ROUTER_ARCHIVED

    def starting(self):
        return self.status == ROUTER_STARTING

    def running(self):
        return self.status == ROUTER_RUNNING

    def stopping(self):
        return self.status == ROUTER_STOPPING

    def stopped(self):
        return self.status == ROUTER_STOPPED

    # The following are to keep the implementation of this stuff in the model
    # rather than potentially multiple external places.
    def set_status_starting(self):
        self.status = ROUTER_STARTING

    def set_status_started(self):
        self.status = ROUTER_RUNNING

    def set_status_stopping(self):
        self.status = ROUTER_STOPPING

    def set_status_stopped(self):
        self.status = ROUTER_STOPPED

    def set_status_finished(self):
        self.archive_status = ROUTER_ARCHIVED

    def __unicode__(self):
        return self.name

    def get_inbound_connector(self):
        return GoConnector.for_router(
            self.router_type, self.key, GoConnector.INBOUND)

    def get_outbound_connector(self):
        return GoConnector.for_router(
            self.router_type, self.key, GoConnector.OUTBOUND)


class RouterStore(PerAccountStore):
    def setup_proxies(self):
        self.routers = self.manager.proxy(Router)

    def list_routers(self):
        return self.list_keys(self.routers)

    def get_router_by_key(self, key):
        return self.routers.load(key)

    @Manager.calls_manager
    def new_router(self, router_type, name, description, config,
                   batch_id, **fields):
        router_id = uuid4().get_hex()

        router = self.routers(
            router_id, user_account=self.user_account_key,
            router_type=router_type, name=name, description=description,
            config=config, batch=batch_id, **fields)

        router = yield router.save()
        returnValue(router)

    def list_running_routers(self):
        return self.routers.index_keys('status', ROUTER_RUNNING)

    def list_active_routers(self):
        return self.routers.index_keys('archive_status', ROUTER_ACTIVE)

    def load_all_bunches(self, keys):
        # Convenience to avoid the extra attribute lookup everywhere.
        return self.routers.load_all_bunches(keys)
