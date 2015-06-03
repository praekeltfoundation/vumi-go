from go.base.celery_routers import CeleryRegexRouter
from go.base.tests.helpers import GoDjangoTestCase


class TestCeleryRegexRouter(GoDjangoTestCase):
    def test_router_for_task_match(self):
        router = CeleryRegexRouter(r'[^a]+', 'foo')
        self.assertEqual(router.route_for_task('bbb'), {'queue': 'foo'})
        self.assertEqual(router.route_for_task('ccc'), {'queue': 'foo'})

    def test_router_for_task_non_match(self):
        router = CeleryRegexRouter(r'[^a]+', 'foo')
        self.assertEqual(router.route_for_task('aaa'), None)
