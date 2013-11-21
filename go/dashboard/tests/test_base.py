from go.base.tests.utils import VumiGoDjangoTestCase


from go.dashboard.tests.utils import FakeDiamondashApiClient
from go.dashboard.base import (
    DashboardSyncError, DashboardParseError,
    Dashboard, DashboardLayout, ConversationDashboardLayout,
    visit_dicts, ensure_handler_fields)


class ToyDashboardLayout(DashboardLayout):
    @ensure_handler_fields('name')
    def handle_foo_metric(self, target):
        return "foo.%s" % target['name']

    @ensure_handler_fields('name')
    def handle_bar_metric(self, target):
        return "bar.%s" % target['name']


class TestDashboardApiClient(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestDashboardApiClient, self).setUp()

        # test using the fake client, we only stub the requests and responses,
        # not the methods that delegate to them
        self.client = FakeDiamondashApiClient()

    def test_make_api_url(self):
        self.assertEqual(
            self.client.make_api_url('dashboards'),
            'http://localhost:7115/api/dashboards')

    def test_replace_dashboard(self):
        self.client.replace_dashboard({'some': 'dashboard'})
        self.assertEqual(self.client.get_requests(), [{
            'method': 'put',
            'url': 'dashboards',
            'data': {'some': 'dashboard'},
        }])


class TestDashboard(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestDashboard, self).setUp()
        self.diamondash_api = FakeDiamondashApiClient()

        layout = ToyDashboardLayout([{
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

        self.monkey_patch(Dashboard, 'api_client', self.diamondash_api)

        self.dashboard = Dashboard(
            'ackbar-the-dashboard',
            'Ackbar the Dashboard',
            layout)

    def tearDown(self):
        super(TestDashboard, self).setUp()

    def test_sync(self):
        self.assertEqual(self.dashboard.serialize(), None)
        self.diamondash_api.set_response({'happy': 'config'})

        self.dashboard.sync()
        [request] = self.diamondash_api.get_requests()

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

    def test_sync_for_error_responses(self):
        self.diamondash_api.set_error_response(404, ':(')
        self.assertRaises(DashboardSyncError, self.dashboard.sync)


class TestDashboardLayout(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestDashboardLayout, self).setUp()
        self.layout = ToyDashboardLayout()

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

    def test_metric_handling(self):
        self.assertEqual(
            self.layout.handle_metric({
                'metric_type': 'foo',
                'name': 'ham',
            }),
            'foo.ham')

        self.assertEqual(
            self.layout.handle_bar_metric({
                'metric_type': 'bar',
                'name': 'spam',
            }),
            'bar.spam')

    def test_metric_handling_for_field_checking(self):
        self.assertRaises(
            DashboardParseError,
            self.layout.handle_metric,
            {'metric_type': 'foo'})

        self.assertRaises(
            DashboardParseError,
            self.layout.handle_bar_metric,
            {'metric_type': 'bar'})

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


class TestConversationDashboardLayout(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestConversationDashboardLayout, self).setUp()
        self.setup_user_api()
        self.conv = self.create_conversation()
        self.layout = ConversationDashboardLayout(self.conv)

    def test_conversation_metric_handling(self):
        self.assertEqual(
            self.layout.handle_metric({
                'metric_type': 'conversation',
                'name': 'foo',
            }),
            "campaigns.%s.conversations.%s.foo" %
            (self.conv.user_account.key, self.conv.key))

    def test_conversation_metric_handling_for_missing_fields(self):
        self.layout.handle_metric({
            'metric_type': 'conversation',
            'name': 'foo',
        })

        self.assertRaises(
            DashboardParseError,
            self.layout.handle_metric,
            {'metric_type': 'conversation'})

    def test_account_metric_handling(self):
        self.assertEqual(
            self.layout.handle_metric({
                'metric_type': 'account',
                'store': 'red',
                'name': 'foo',
            }),
            "campaigns.%s.stores.red.foo" %
            (self.conv.user_account.key))

    def test_account_metric_handling_for_missing_fields(self):
        self.layout.handle_metric({
            'metric_type': 'account',
            'store': 'red',
            'name': 'foo',
        })

        self.assertRaises(
            DashboardParseError,
            self.layout.handle_metric,
            {'metric_type': 'account',
             'store': 'red'})

        self.assertRaises(
            DashboardParseError,
            self.layout.handle_metric,
            {'metric_type': 'account',
             'name': 'foo'})
