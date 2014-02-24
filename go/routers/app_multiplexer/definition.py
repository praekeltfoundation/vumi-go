from go.vumitools.router.definition import RouterDefinitionBase


class RouterDefinition(RouterDefinitionBase):
    router_type = 'app_multiplexer'

    def configured_outbound_endpoints(self, config):
        endpoints = [entry['endpoint'] for entry in config.get('entries', [])]
        return list(set(endpoints))
