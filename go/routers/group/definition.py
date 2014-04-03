from go.vumitools.router.definition import RouterDefinitionBase


class RouterDefinition(RouterDefinitionBase):
    router_type = 'group'

    def configured_outbound_endpoints(self, config):
        return ('selected')
