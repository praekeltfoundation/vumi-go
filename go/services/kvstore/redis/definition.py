
from vumi.config import ConfigInt, ConfigText

from go.services.kvstore.redis.service_component import (
    RedisKVStoreServiceComponent)
from go.vumitools.service.definition import ServiceComponentDefinitionBase


class RedisKVStoreServiceComponentConfig(
        ServiceComponentDefinitionBase.CONFIG_CLASS):
    key_prefix = ConfigText("Redis key prefix.", static=True, required=True)
    keys_per_user = ConfigInt(
        "Maximum number of keys each user may make use of.", static=True,
        default=100)


class ServiceComponentDefinition(ServiceComponentDefinitionBase):
    service_component_type = 'kvstore.redis'
    service_component_display_name = 'Key-value store (Redis)'
    service_component_factory = RedisKVStoreServiceComponent
    service_component_interfaces = ('kvstore',)
    CONFIG_CLASS = RedisKVStoreServiceComponentConfig
