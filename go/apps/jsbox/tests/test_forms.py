
from django.test import TestCase

from go.apps.jsbox.forms import (JsboxForm, JsboxAppConfigForm,
                                 JsboxAppConfigFormset)


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
