# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

import os

from celery.app import app_or_default

from go.vumitools.api import VumiApiCommand


class CeleryTestMixIn(object):

    def setup_celery_for_tests(self):
        """Setup celery for tests."""
        celery_config = os.environ.get("CELERY_CONFIG_MODULE")
        os.environ["CELERY_CONFIG_MODULE"] = "celery.tests.config"
        self._app = app_or_default()
        always_eager = self._app.conf.CELERY_ALWAYS_EAGER
        self._app.conf.CELERY_ALWAYS_EAGER = True
        self._old_celery = celery_config, always_eager

    def restore_celery(self):
        celery_config, always_eager = self._old_celery
        if celery_config is None:
            del os.environ["CELERY_CONFIG_MODULE"]
        else:
            os.environ["CELERY_CONFIG_MODULE"] = celery_config
        self._app.conf.CELERY_ALWAYS_EAGER = always_eager

    def get_consumer(self, **options):
        connection = self._app.broker_connection()
        consumer = self._app.amqp.TaskConsumer(connection=connection,
                                               **options)
        return consumer

    def fetch_cmds(self, consumer):
        msgs = []
        while True:
            msg = consumer.fetch()
            if msg is not None:
                msgs.append(msg.payload)
            else:
                break
        return [VumiApiCommand(**payload) for payload in msgs]
