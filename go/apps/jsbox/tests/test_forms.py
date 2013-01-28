import mock

from django.test import TestCase

from go.apps.jsbox.forms import (JsboxForm, JsboxAppConfigForm,
                                 JsboxAppConfigFormset,
                                 possibly_load_from_url)


class PossiblyLoadFromUrlTestCase(TestCase):
    def mock_response(self, status_code, text):
        r = mock.Mock()
        r.status_code = status_code
        r.text = text
        r.ok = status_code == 200
        return r

    @mock.patch('requests.get')
    def test_blank_url(self, requests_get):
        value = possibly_load_from_url('', 'foo', True)
        self.assertEqual(value, 'foo')
        self.assertEqual(requests_get.call_count, 0)

    @mock.patch('requests.get')
    def test_update_false(self, requests_get):
        value = possibly_load_from_url('http://www.example.com', 'foo', False)
        self.assertEqual(value, 'foo')
        self.assertEqual(requests_get.call_count, 0)

    @mock.patch('requests.get')
    def test_successful_request(self, requests_get):
        requests_get.return_value = self.mock_response(200, 'source text')
        value = possibly_load_from_url('http://www.example.com', 'foo', True)
        self.assertEqual(value, 'source text')
        requests_get.assert_called_once_with('http://www.example.com')

    @mock.patch('requests.get')
    def test_failed_request(self, requests_get):
        requests_get.return_value = self.mock_response(500, 'error text')
        value = possibly_load_from_url('http://www.example.com', 'foo', True)
        self.assertEqual(value, 'foo')
        requests_get.assert_called_once_with('http://www.example.com')


class JsboxFormTestCase(TestCase):
    def test_initial_form_metadata(self):
        initial = JsboxForm.initial_from_metadata({
            'javascript': 'x = 1;',
            'source_url': 'http://www.example.com',
        })
        self.assertEqual(initial, {
            'javascript': 'x = 1;',
            'source_url': 'http://www.example.com',
        })

    def test_to_metadata(self):
        form = JsboxForm(data={
            'javascript': 'x = 1;',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_metadata()
        self.assertEqual(metadata, {
            'javascript': 'x = 1;',
            'source_url': '',
        })

    @mock.patch('go.apps.jsbox.forms.possibly_load_from_url')
    def test_update_from_source(self, possibly_load):
        possibly_load.return_value = "custom javascript"
        source_url = 'http://www.example.com/'
        form = JsboxForm(data={
            'javascript': '',
            'source_url': source_url,
            'update_from_source': '1',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_metadata()
        possibly_load.assert_called_once_with(source_url, '', True)
        self.assertEqual(metadata, {
            'javascript': possibly_load.return_value,
            'source_url': source_url,
        })


class JsboxAppConfigFormTestCase(TestCase):
    def test_initial_from_metadata(self):
        initial = JsboxAppConfigForm.initial_from_metadata({
            'key': 'foo',
            'value': 'bar',
            'source_url': 'http://www.example.com',
        })
        self.assertEqual(initial, {
            'key': 'foo',
            'value': 'bar',
            'source_url': 'http://www.example.com',
        })

    def test_to_metadata(self):
        form = JsboxAppConfigForm(data={
            'key': 'foo',
            'value': 'bar',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_metadata()
        self.assertEqual(metadata, {
            'key': 'foo',
            'value': 'bar',
            'source_url': '',
        })

    @mock.patch('go.apps.jsbox.forms.possibly_load_from_url')
    def test_update_from_source(self, possibly_load):
        possibly_load.return_value = "custom javascript"
        source_url = 'http://www.example.com/'
        form = JsboxAppConfigForm(data={
            'key': 'bar',
            'value': '',
            'source_url': source_url,
            'update_from_source': '1',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_metadata()
        possibly_load.assert_called_once_with(source_url, '', True)
        self.assertEqual(metadata, {
            'key': 'bar',
            'value': possibly_load.return_value,
            'source_url': source_url,
        })


class JsboxAppConfigFormsetTestCase(TestCase):
    def test_initial_from_metadata(self):
        initials = JsboxAppConfigFormset.initial_from_metadata({
            'foo1': {'value': 'bar', 'source_url': 'http://example.com/1'},
            'foo2': {'value': 'baz', 'source_url': 'http://example.com/2'},
        })
        self.assertEqual(initials, [
           {'key': 'foo1', 'value': 'bar',
            'source_url': 'http://example.com/1'},
           {'key': 'foo2', 'value': 'baz',
            'source_url': 'http://example.com/2'},
        ])

    def test_to_metadata(self):
        formset = JsboxAppConfigFormset(data={
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MAX_NUM_FORMS': u'',
            'form-0-key': 'foo1',
            'form-0-value': 'bar',
            'form-0-source_url': 'http://example.com/1',
        })
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.to_metadata(), {
            'foo1': {'value': 'bar', 'source_url': 'http://example.com/1'},
        })
