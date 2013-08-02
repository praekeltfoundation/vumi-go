"""Tests for go.api.go_api.utils."""

from twisted.trial.unittest import TestCase

from go.api.go_api.utils import GoApiError


class GoApiErrorTestCase(TestCase):
    def test_go_api_error(self):
        err = GoApiError("Testing")
        self.assertEqual(err.faultString, "Testing")
        self.assertEqual(err.faultCode, 400)

    def test_go_api_error_with_fault_code(self):
        err = GoApiError("Other", fault_code=314)
        self.assertEqual(err.faultString, "Other")
        self.assertEqual(err.faultCode, 314)
