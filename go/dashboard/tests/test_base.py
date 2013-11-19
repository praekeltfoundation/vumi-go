from go.vumitools.tests.utils import GoTestCase
from go.base.tests.utils import FakeResponse, FakeServer

from go.dashboard.base import (
    DashboardSyncError, DashboardParseError,
    Dashboard, DashboardLayout, visit_dicts)


class FakeDiamondashResponse(FakeResponse):
    def __init__(self, data=None, code=200):
        data = self.make_response_data(data)
        super(FakeDiamondashResponse, self).__init__(data=data, code=code)

    def make_response_data(self, data=None):
        return {
            'success': True,
            'data': data
        }


class FakeDiamondashErrorResponse(FakeResponse):
    def __init__(self, message, code):
        data = self.make_response_data(message)
        super(FakeDiamondashErrorResponse, self).__init__(data=data, code=code)

    def make_response_data(self, message):
        return {
            'success': False,
            'message': message
        }


class ToyLayout(DashboardLayout):
    def handle_foo_metric(self, target):
        return "foo.%s" % target['name']

    def handle_bar_metric(self, target):
        return "bar.%s" % target['name']


class TestDashboard(GoTestCase):
    def setUp(self):
        super(TestDashboard, self).setUp()
        self.diamondash = FakeServer()

        layout = ToyLayout([{
            'type': 'lvalue',
            'time_range': '1d',
            'title': 'Spam (24h)',
            'target': {
                'metric_type': 'foo',
                'name': 'spam',
            },
        }, {
            'type': 'lvalue',
            'time_range': '1d',
            'title': 'Ham (24h)',
            'target': {
                'metric_type': 'foo',
                'name': 'ham',
            },
        }])

        self.dashboard = Dashboard(
            'ackbar-the-dashboard',
            'Ackbar the Dashboard',
            layout)

    def tearDown(self):
        super(TestDashboard, self).setUp()

    def test_sync(self):
        self.assertEqual(self.dashboard.serialize(), None)

        resp = FakeDiamondashResponse({'happy': 'config'})
        self.diamondash.set_response(resp)

        self.dashboard.sync()
        [request] = self.diamondash.get_requests()

        self.assertEqual(request['method'], 'put')

        self.assertEqual(
            request['url'],
            'http://localhost:7115/api/dashboards')

        self.assertEqual(request['data'], {
            'name': 'ackbar-the-dashboard',
            'title': 'Ackbar the Dashboard',
            'widgets': [{
                'type': 'lvalue',
                'time_range': '1d',
                'title': 'Spam (24h)',
                'target': 'foo.spam',
            }, {
                'type': 'lvalue',
                'time_range': '1d',
                'title': 'Ham (24h)',
                'target': 'foo.ham',
            }]
        })
        self.assertEqual(self.dashboard.serialize(), {'happy': 'config'})

    def test_sync_for_api_error_responses(self):
        resp = FakeDiamondashErrorResponse(':(', code=400)
        self.diamondash.set_response(resp)
        self.assertRaises(DashboardSyncError, self.dashboard.sync)

    def test_sync_for_error_responses(self):
        resp = FakeResponse('Gateway Timeout', code=504)
        self.diamondash.set_response(resp)
        self.assertRaises(DashboardSyncError, self.dashboard.sync)


class TestDashboardLayout(GoTestCase):
    def setUp(self):
        super(TestDashboardLayout, self).setUp()
        self.layout = ToyLayout()

    def test_visit_dicts(self):
        def traverse(collection):
            collection['visited'] = True
            return collection

        collection = {
            'a': 'cake',
            'b': {'foo': 'bar'},
        }
        visit_dicts(collection, traverse)
        self.assertEqual(collection, {
            'a': 'cake',
            'b': {
                'visited': True,
                'foo': 'bar',
            }
        })

        collection = [{
            'a': 'cake',
            'b': {'foo': 'bar'}
        }, {
            'c': 'fish',
            'd': {'baz': 'qux'}
        }]
        visit_dicts(collection, traverse)
        self.assertEqual(collection, [{
            'visited': True,
            'a': 'cake',
            'b': {
                'visited': True,
                'foo': 'bar',
            },
        }, {
            'visited': True,
            'c': 'fish',
            'd': {
                'visited': True,
                'baz': 'qux',
            },
        }])

        collection = [{
            'a': 'cake',
            'b': {'foo': 'bar'}
        }, {
            'c': 'fish',
            'd': {
                'baz': [{
                    'spam': {'lerp': 'larp'},
                }]
            }
        }]
        visit_dicts(collection, traverse)
        self.assertEqual(collection, [{
            'visited': True,
            'a': 'cake',
            'b': {
                'visited': True,
                'foo': 'bar',
            }
        }, {
            'visited': True,
            'c': 'fish',
            'd': {
                'visited': True,
                'baz': [{
                    'visited': True,
                    'spam': {
                            # pep8 or pyflakes somehow isn't happy with this
                            # being indented properly
                            'visited': True,
                            'lerp': 'larp',
                    },
                }]
            }
        }])

    def test_new_row_adding(self):
        self.assertEqual(self.layout.serialize(), [])
        self.layout.new_row()
        self.assertEqual(self.layout.serialize(), ['new_row'])

    def test_widget_adding(self):
        self.assertEqual(self.layout.serialize(), [])

        self.layout.add_widget({
            'name': 'windu-the-widget',
            'target': {
                'metric_type': 'foo',
                'name': 'spam'
            }
        })

        self.layout.add_widget({
            'name': 'yaddle-the-widget',
            'metrics': [{
                'target': {
                    'metric_type': 'foo',
                    'name': 'lerp'
                }
            }, {
                'target': {
                    'metric_type': 'bar',
                    'name': 'larp'
                }
            }]
        })

        self.assertEqual(self.layout.serialize(), [{
            'name': 'windu-the-widget',
            'target': 'foo.spam',
        }, {
            'name': 'yaddle-the-widget',
            'metrics': [
                {'target': 'foo.lerp'},
                {'target': 'bar.larp'}]
        }])

    def test_widget_adding_for_foreign_metric_types(self):
        self.assertRaises(
            DashboardParseError,
            self.layout.add_widget,
            {
                'name': 'anakin-the-widget',
                'target': {
                    'metric_type': 'baz',
                    'name': 'spam'
                }
            })
