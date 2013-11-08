# -*- coding: utf-8 -*-

from mock import Mock
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.test_sandbox import (
    ResourceTestCaseBase, DummyAppWorker)

from go.apps.jsbox.optout import OptoutResource
from go.vumitools.tests.utils import GoPersistenceMixin


class StubbedAppWorker(DummyAppWorker):
    def __init__(self):
        super(StubbedAppWorker, self).__init__()
        self.user_api = Mock()

    def user_api_for_api(self, api):
        return self.user_api


class OptoutResourceTestCase(ResourceTestCaseBase, GoPersistenceMixin):
    use_riak = True
    app_worker_cls = StubbedAppWorker
    resource_cls = OptoutResource

    @inlineCallbacks
    def setUp(self):
        super(OptoutResourceTestCase, self).setUp()
        yield self._persist_setUp()

    def tearDown(self):
        super(OptoutResourceTestCase, self).tearDown()
        return self._persist_tearDown()

    def test_something(self):
        True
