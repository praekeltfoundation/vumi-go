import uuid

from twisted.internet.defer import inlineCallbacks
from vumi_wikipedia.tests import test_wikipedia

from go.vumitools.tests.utils import GoAppWorkerTestMixin
from go.apps.wikipedia.vumi_app import WikipediaApplication


class WikipediaApplicationTestCase(GoAppWorkerTestMixin,
                                   test_wikipedia.WikipediaWorkerTestCase):
    application_class = WikipediaApplication
    use_riak = True

    @inlineCallbacks
    def setUp(self):
        yield super(WikipediaApplicationTestCase, self).setUp()

        # Steal app's vumi_api
        self.vumi_api = self.worker.vumi_api  # YOINK!
        self._persist_riak_managers.append(self.vumi_api.manager)

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)

        # Add tags
        yield self.setup_tagpools()

        # Give a user access to a tagpool
        self.user_api.api.account_store.tag_permissions(uuid.uuid4().hex,
            tagpool=u"pool", max_keys=None)

        self.conv = yield self.create_conversation(
            delivery_tag_pool=u'pool', delivery_class=u'sms')

    def mkmsg_in(self, *args, **kw):
        msg = super(WikipediaApplicationTestCase, self).mkmsg_in(*args, **kw)
        self.conv.set_go_helper_metadata(msg['helper_metadata'])
        return msg

    def assert_metrics(self, expected_metrics):
        # We aren't collecting these.
        pass

    def test_no_metrics_prefix(self):
        # This isn't supported.
        pass
