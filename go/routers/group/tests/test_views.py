from go.base.tests.helpers import GoDjangoTestCase
from go.routers.tests.view_helpers import RouterViewsHelper


class GroupViewTests(GoDjangoTestCase):

    def setUp(self):
        self.router_helper = self.add_helper(RouterViewsHelper(u'group'))
        self.user_helper = self.router_helper.vumi_helper.get_or_create_user()
        self.client = self.router_helper.get_client()
