

class ModelStore(object):
    def __init__(self, manager, user):
        self.base_manager = manager
        self.set_user(user)

    def set_user(self, user):
        self.user = user
        self.manager = self.base_manager.sub_manager(user)
        self.setup_proxies()

    def setup_proxies(self):
        pass
