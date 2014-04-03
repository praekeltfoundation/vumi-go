from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.routers.group.vumi_app import GroupRouter
from go.routers.tests.helpers import RouterWorkerHelper


class TestGroupRouter(VumiTestCase):

    router_class = GroupRouter

    @inlineCallbacks
    def setUp(self):
        self.router_helper = self.add_helper(RouterWorkerHelper(GroupRouter))
        self.router_worker = yield self.router_helper.get_router_worker({})
