# -*- test-case-name: go.apps.http_api.tests.test_vumi_app -*-
from twisted.web import resource

from vumi.application.base import ApplicationWorker
from vumi.transports.httprpc import httprpc


class StreamingResource(resource.Resource):
    """
    Streams messages as they arrive on a consumer.
    """
    def __init__(self, worker):
        resource.Resource.__init__(self)
        self.worker = worker


class StreamingHTTPWorker(ApplicationWorker):
    """

    :param str web_path:
        The path the HTTP worker should expose the API on
    :param int web_port:
        The port the HTTP worker should open for the API
    :param str health_path:
        The path the resource should receive health checks on.
        Defaults to '/health/'
    """

    def validate_config(self):
        self.web_path = self.config['web_path']
        self.web_port = int(self.config['web_port'])
        self.health_path = self.config.get('health_path', '/health/')

    def setup_application(self):
        self.webserver = self.start_web_resources([
            (StreamingResource(self), self.web_path),
            (httprpc.HttpRpcHealthResource(self), self.health_path),
            ], self.web_port)

    def teardown_application(self):
        self.webserver.loseConnection()
