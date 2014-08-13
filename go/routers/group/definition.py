from go.vumitools.router.definition import RouterDefinitionBase


class RouterDefinition(RouterDefinitionBase):
    router_type = 'group'

    def configured_outbound_endpoints(self, config):
        endpoints = [entry['endpoint'] for entry in config.get('rules', [])]
        return list(set(endpoints))
