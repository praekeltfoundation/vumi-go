

class MetricsStoreServiceComponent(object):
    def __init__(self, service_def):
        self.service_def = service_def
        self.config = service_def.get_config()
