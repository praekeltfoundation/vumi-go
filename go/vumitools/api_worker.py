# -*- test-case-name: go.vumitools.tests.test_api_worker -*-
# -*- coding: utf-8 -*-

"""Vumi application worker for the vumitools API."""

from vumi.application import ApplicationWorker


class VumiApiWorker(ApplicationWorker):

    # TODO: Vumi application worker will need to grow
    #       support for sending messages that are not
    #       replies

    def validate_config(self):
        pass

    def setup_application(self):
        pass

    def teardown_application(self):
        pass

    def consume_ack(self, event):
        pass

    def consume_delivery_report(self, event):
        pass

    def consume_user_message(self, msg):
        pass

    def close_session(self, msg):
        pass
