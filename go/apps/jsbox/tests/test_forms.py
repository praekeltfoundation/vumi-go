import mock

from django.test import TestCase

from go.apps.jsbox.forms import JsboxForm


class JsboxFormTestCase(TestCase):
    def test_to_metdata(self):
        form = JsboxForm(data={
            'javascript': 'x = 1;',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_metadata()
        self.assertEqual(metadata, {
            'javascript': 'x = 1;',
            'source_url': '',
        })

    def mock_response(self, status_code, text):
        r = mock.Mock()
        r.status_code = status_code
        r.text = text
        return r

    @mock.patch('requests.get')
    def test_update_from_source(self, requests_get):
        requests_get.return_value = self.mock_response(
            "200", "custom javascript")
        source_url = 'http://www.example.com/'
        form = JsboxForm(data={
            'javascript': '',
            'source_url': source_url,
            'update_from_source': '1',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_metadata()
        requests_get.assert_called_once_with(source_url)
        self.assertEqual(metadata, {
            'javascript': requests_get.return_value.text,
            'source_url': source_url,
        })
