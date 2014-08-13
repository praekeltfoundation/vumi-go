# -*- test-case-name: go.apps.wikipedia.tests.test_vumi_app -*-
from twisted.internet.defer import inlineCallbacks

from vumi.blinkenlights.metrics import Metric
from vumi_wikipedia.wikipedia import WikipediaWorker, TimerWrapper

from go.vumitools.app_worker import (
    GoApplicationMixin, GoApplicationConfigMixin)


class WikipediaConfig(WikipediaWorker.CONFIG_CLASS, GoApplicationConfigMixin):
    pass


class WikipediaApplication(WikipediaWorker, GoApplicationMixin):
    CONFIG_CLASS = WikipediaConfig
    worker_name = 'wikipedia_ussd_application'

    def validate_config(self):
        super(WikipediaApplication, self).validate_config()

    def _setup_metrics(self, metrics_prefix):
        # We don't want to use the underlying app's metrics.
        self.metrics = None

    @inlineCallbacks
    def setup_application(self):
        yield super(WikipediaApplication, self).setup_application()
        yield self._go_setup_worker()

    @inlineCallbacks
    def teardown_application(self):
        yield super(WikipediaApplication, self).teardown_application()
        yield self._go_teardown_worker()

    def fire_metric(self, config, metric_name, metric_suffix=None, value=1):
        # Don't try to collect metrics.
        pass

    def get_timer_metric(self, config, metric_name):
        metrics = self.get_conversation_metric_manager(config.conversation)
        metric = Metric(metric_name)
        # TODO: Make this less horrible.
        metric.set = lambda value: fire_oneshot_metric(metrics, metric, value)
        return TimerWrapper(metric)

    def get_config(self, msg):
        return self.get_message_config(msg)

    def send_sms_non_reply(self, msg, config, sms_content):
        helper_metadata = {}
        config.conversation.set_go_helper_metadata(helper_metadata)
        return self.send_to(
            msg['from_addr'], sms_content, transport_type='sms',
            endpoint='sms_content', helper_metadata=helper_metadata)


def fire_oneshot_metric(metrics, metric, value):
    metrics.oneshot(metric, value)
    metrics.publish_metrics()
