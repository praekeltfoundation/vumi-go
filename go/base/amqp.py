import time

from kombu import Connection, Exchange

from vumi.blinkenlights.metrics import MetricMessage


class AmqpConnection(object):
    """
    Connect to the AMQP backend for easy publishing without
    having to hack our way through Celery.
    """
    def __init__(self):
        self.conn = None
        self.default_exchange = Exchange('vumi', 'direct', durable=True)
        self.metrics_exchange = Exchange('vumi.metrics', 'direct',
            durable=True)

    def connect(self, dsn=None):
        if dsn is None:
            from django.conf import settings
            dsn = 'librabbitmq://%s:%s@%s:%s/%s' % (
                settings.BROKER_USER,
                settings.BROKER_PASSWORD,
                settings.BROKER_HOST,
                settings.BROKER_PORT,
                settings.BROKER_VHOST)

        self.conn = Connection(dsn)
        self.producer = self.conn.Producer()

    def is_connected(self):
        return self.conn and self.conn.connected

    def publish(self, message, exchange, routing_key):
        self.producer.publish(message, exchange=exchange,
            routing_key=routing_key)

    def publish_command_message(self, command):
        return self.publish(command.to_json(), exchange=self.default_exchange,
            routing_key='vumi.api')

    def publish_metric_message(self, metric):
        return self.publish(metric.to_json(), exchange=self.metrics_exchange,
            routing_key='vumi.metrics')

    def publish_metric(self, metric_name, aggregators, value, timestamp=None):
        timestamp = timestamp or time.time()
        metric_msg = MetricMessage()
        metric_msg.append((metric_name,
            tuple(sorted(agg.name for agg in aggregators)),
            [(timestamp, value)]))
        return self.publish_metric_message(metric_msg)

connection = AmqpConnection()


def connect(dsn=None):
    if not connection.is_connected():
        connection.connect(dsn)
