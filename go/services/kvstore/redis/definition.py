from go.vumitools.service.definition import ServiceComponentDefinitionBase


class ServiceComponentDefinition(ServiceComponentDefinitionBase):
    service_component_type = 'kvstore.redis'
    service_component_display_name = 'Key-value store (Redis)'
