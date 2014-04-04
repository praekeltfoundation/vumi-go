

class MetricsStoreServiceComponent(object):
    def __init__(self, service_def):
        self.service_def = service_def
        self.service = service_def.service
