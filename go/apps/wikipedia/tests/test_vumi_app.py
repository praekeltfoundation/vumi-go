from vumi_wikipedia.tests import test_wikipedia

from go.vumitools.tests.utils import GoPersistenceMixin
from go.apps.wikipedia.vumi_app import WikipediaApplication


class WikipediaApplicationTestCase(GoPersistenceMixin,
                                   test_wikipedia.WikipediaWorkerTestCase):
    application_class = WikipediaApplication
    use_riak = True

    def assert_metrics(self, expected_metrics):
        # We aren't collecting these.
        pass

    def test_no_metrics_prefix(self):
        # This isn't supported.
        pass
