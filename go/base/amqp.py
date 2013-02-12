from kombu import Connection, Exchange


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

    def connect(self, dsn):
        self.conn = Connection(dsn)
        self.producer = self.conn.Producer()

    def is_connected(self):
        return self.conn and self.conn.connected

    def publish(self, message, exchange, routing_key):
        self.producer.publish(message, exchange=exchange,
            routing_key=routing_key)

    def publish_command(self, command):
        return self.publish(command.to_json, exchange=self.default_exchange,
            routing_key='vumi.api')

    def publish_metric(self, metric):
        return self.publish(metric.to_json(), exchange=self.metrics_exchange,
            routing_key='vumi.metrics')

connection = AmqpConnection()


def connect(dsn):
    if not connection.is_connected():
        connection.connect(dsn)
