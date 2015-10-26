"""Test for go.base.decorators."""

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase
    from go.base.decorators import render_exception
    from django.template.response import TemplateResponse


class CatchableDummyError(Exception):
    """Error that will be caught by DummyView.post."""


class UncatchableDummyError(Exception):
    """Error that will not be caught by DummyView.post."""


class DummyView(object):
    @render_exception(CatchableDummyError, 400, "Meep.")
    def post(self, request, err=None):
        if err is None:
            return "Success"
        raise err


class TestRenderException(GoDjangoTestCase):

    def test_no_exception(self):
        d = DummyView()
        self.assertEqual(d.post("request"), "Success")

    def test_expected_exception(self):
        d = DummyView()
        self.assertRaises(
            UncatchableDummyError, d.post, "request", UncatchableDummyError())

    def test_other_exception(self):
        d = DummyView()
        response = d.post("request", CatchableDummyError("foo"))
        self.assertTrue(isinstance(response, TemplateResponse))
        self.assertEqual(response.template_name, 'error.html')
        self.assertEqual(response.status_code, 400)
