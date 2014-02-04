from go.vumitools.router.definition import RouterDefinitionBase


class RouterDefinition(RouterDefinitionBase):
    router_type = 'application_multiplexer'

    def configured_outbound_endpoints(self, config):
        return list(set(config.get('keyword_endpoint_mapping', {}).values()))
