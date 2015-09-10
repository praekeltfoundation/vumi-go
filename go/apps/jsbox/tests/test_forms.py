from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.apps.jsbox.forms import (
        JsboxForm, JsboxAppConfigForm, JsboxAppConfigFormset)
    from go.base.tests.helpers import GoDjangoTestCase


class TestJsboxForm(GoDjangoTestCase):
    def test_initial_form_metadata(self):
        initial = JsboxForm.initial_from_config({
            'javascript': 'x = 1;',
            'source_url': 'http://www.example.com',
        })
        self.assertEqual(initial, {
            'javascript': 'x = 1;',
            'source_url': 'http://www.example.com',
        })

    def test_to_config(self):
        form = JsboxForm(data={
            'javascript': 'x = 1;',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_config()
        self.assertEqual(metadata, {
            'javascript': 'x = 1;',
            'source_url': '',
        })


class TestJsboxAppConfigForm(GoDjangoTestCase):
    def test_initial_from_config(self):
        initial = JsboxAppConfigForm.initial_from_config({
            'key': 'foo',
            'value': 'bar',
            'source_url': 'http://www.example.com',
        })
        self.assertEqual(initial, {
            'key': 'foo',
            'value': 'bar',
            'source_url': 'http://www.example.com',
        })

    def test_to_config(self):
        form = JsboxAppConfigForm(data={
            'key': 'foo',
            'value': 'bar',
        })
        self.assertTrue(form.is_valid())
        metadata = form.to_config()
        self.assertEqual(metadata, {
            'key': 'foo',
            'value': 'bar',
            'source_url': '',
        })


class TestJsboxAppConfigFormset(GoDjangoTestCase):
    def test_initial_from_config(self):
        initials = JsboxAppConfigFormset.initial_from_config({
            'foo1': {'value': 'bar', 'source_url': 'http://example.com/1'},
            'foo2': {'value': 'baz', 'source_url': 'http://example.com/2'},
        })
        self.assertEqual(initials, [
            {'key': 'foo1', 'value': 'bar',
             'source_url': 'http://example.com/1'},
            {'key': 'foo2', 'value': 'baz',
             'source_url': 'http://example.com/2'},
        ])

    def test_to_config(self):
        formset = JsboxAppConfigFormset(data={
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MAX_NUM_FORMS': u'',
            'form-0-key': 'foo1',
            'form-0-value': 'bar',
            'form-0-source_url': 'http://example.com/1',
        })
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.to_config(), {
            'foo1': {'value': 'bar', 'source_url': 'http://example.com/1'},
        })
