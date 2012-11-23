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
