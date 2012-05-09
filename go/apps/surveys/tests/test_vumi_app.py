# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

import json

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent, TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis
from vumi.persist.txriak_manager import TxRiakManager

from go.apps.surveys.vumi_app import SurveyApplication
from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
from go.vumitools.tests.utils import CeleryTestMixIn, DummyConsumerFactory
from go.vumitools.account import AccountStore


def dummy_consumer_factory_factory_factory(publish_func):
    def dummy_consumer_factory_factory():
        dummy_consumer_factory = DummyConsumerFactory()
        dummy_consumer_factory.publish = publish_func
        return dummy_consumer_factory
    return dummy_consumer_factory_factory


class TestSurveyApplication(ApplicationTestCase, CeleryTestMixIn):

    application_class = SurveyApplication
    timeout = 2

    @inlineCallbacks
    def setUp(self):
        super(TestSurveyApplication, self).setUp()
        self._fake_redis = FakeRedis()
        self.app = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            'poll_id': '1',
            'riak': {
                'bucket_prefix': 'test.',
                },
            })
        self.cmd_dispatcher = yield self.get_application({
            'transport_name': 'cmd_dispatcher',
            'worker_names': ['survey_application'],
            }, cls=CommandDispatcher)
        self.manager = self.app.store.manager  # YOINK!
        self.account_store = AccountStore(self.manager)
        self.VUMI_COMMANDS_CONSUMER = dummy_consumer_factory_factory_factory(
            self.publish_command)
        self.setup_celery_for_tests()

    @inlineCallbacks
    def tearDown(self):
        self.restore_celery()
        self._fake_redis.teardown()
        yield self.app.manager.purge_all()
        yield super(TestSurveyApplication, self).tearDown()

    def test_hi(self):
        print 'hi'
