from go.base.celery_routers import CeleryAppRouter, CeleryRegexRouter
from go.base.tests.helpers import GoDjangoTestCase


class TestCeleryRegexRouter(GoDjangoTestCase):
    def test_router_for_task_match(self):
        router = CeleryRegexRouter(r'[^a]+', 'foo')
        self.assertEqual(router.route_for_task('bbb'), {'queue': 'foo'})
        self.assertEqual(router.route_for_task('ccc'), {'queue': 'foo'})

    def test_router_for_task_non_match(self):
        router = CeleryRegexRouter(r'[^a]+', 'foo')
        self.assertEqual(router.route_for_task('aaa'), None)


class TestAppRouter(GoDjangoTestCase):
    def test_router_for_task(self):
        router = CeleryAppRouter()

        self.assertEqual(
            router.route_for_task('a.b.c.d'),
            {'queue': 'a.b'})

        self.assertEqual(
            router.route_for_task('foo.bar.baz.quux'),
            {'queue': 'foo.bar'})

        self.assertEqual(
            router.route_for_task('foo.bar'),
            {'queue': 'foo.bar'})

        self.assertEqual(
            router.route_for_task('foo'),
            {'queue': 'foo'})
