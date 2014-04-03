# -*- test-case-name: go.vumitools.service.tests.test_models -*-

from uuid import uuid4
from datetime import datetime

from twisted.internet.defer import returnValue

from vumi.persist.model import Model, Manager
from vumi.persist.fields import Unicode, ForeignKey, Timestamp, Json

from go.vumitools.account import UserAccount, PerAccountStore


SERVICE_COMPONENT_ACTIVE = u'active'
SERVICE_COMPONENT_ARCHIVED = u'archived'

SERVICE_COMPONENT_STARTING = u'starting'
SERVICE_COMPONENT_RUNNING = u'running'
SERVICE_COMPONENT_STOPPING = u'stopping'
SERVICE_COMPONENT_STOPPED = u'stopped'


class ServiceComponent(Model):
    """A service component for exposing interesting functionality."""

    VERSION = 1
    MIGRATOR = None

    user_account = ForeignKey(UserAccount)
    name = Unicode(max_length=255)
    description = Unicode(default=u'')
    service_component_type = Unicode(index=True)
    config = Json(default=dict)

    created_at = Timestamp(default=datetime.utcnow, index=True)
    archived_at = Timestamp(null=True, index=True)

    archive_status = Unicode(default=SERVICE_COMPONENT_ACTIVE, index=True)
    status = Unicode(default=SERVICE_COMPONENT_STOPPED, index=True)

    def active(self):
        return self.archive_status == SERVICE_COMPONENT_ACTIVE

    def archived(self):
        return self.archive_status == SERVICE_COMPONENT_ARCHIVED

    def starting(self):
        return self.status == SERVICE_COMPONENT_STARTING

    def running(self):
        return self.status == SERVICE_COMPONENT_RUNNING

    def stopping(self):
        return self.status == SERVICE_COMPONENT_STOPPING

    def stopped(self):
        return self.status == SERVICE_COMPONENT_STOPPED

    # The following are to keep the implementation of this stuff in the model
    # rather than potentially multiple external places.
    def set_status_starting(self):
        self.status = SERVICE_COMPONENT_STARTING

    def set_status_started(self):
        self.status = SERVICE_COMPONENT_RUNNING

    def set_status_stopping(self):
        self.status = SERVICE_COMPONENT_STOPPING

    def set_status_stopped(self):
        self.status = SERVICE_COMPONENT_STOPPED

    def set_status_finished(self):
        self.archive_status = SERVICE_COMPONENT_ARCHIVED

    def __unicode__(self):
        return self.name


class ServiceComponentStore(PerAccountStore):
    def setup_proxies(self):
        self.service_components = self.manager.proxy(ServiceComponent)

    def list_service_components(self):
        return self.list_keys(self.service_components)

    def get_service_component_by_key(self, key):
        return self.service_components.load(key)

    @Manager.calls_manager
    def new_service_component(self, service_component_type, name, description,
                              config, **fields):
        service_component_id = uuid4().get_hex()

        service_component = self.service_components(
            service_component_id, user_account=self.user_account_key,
            service_component_type=service_component_type, name=name,
            description=description, config=config, **fields)

        service_component = yield service_component.save()
        returnValue(service_component)

    def list_running_service_components(self):
        return self.service_components.index_keys(
            'status', SERVICE_COMPONENT_RUNNING)

    def list_active_service_components(self):
        return self.service_components.index_keys(
            'archive_status', SERVICE_COMPONENT_ACTIVE)

    def load_all_bunches(self, keys):
        # Convenience to avoid the extra attribute lookup everywhere.
        return self.service_components.load_all_bunches(keys)
