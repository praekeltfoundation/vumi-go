"""
Replacement for the runbillingserver management command.
"""

from twisted.web.resource import Resource, getChildForRequest
from txpostgres.reconnection import DeadConnectionDetector

from vumi import log

from go.billing import settings as app_settings
from go.billing.api import Root
from go.billing.utils import DictRowConnectionPool


class DeferredResource(Resource):
    isLeaf = 1

    def __init__(self, d):
        Resource.__init__(self)
        self.d = d
        self.d.addCallback(self._set_resource)
        self._wrapped_resource = None

    def getChild(self, name, request):
        return self

    def render(self, request):
        self.d.addCallback(self._cbChild, request).addErrback(
            self._ebChild, request)
        from twisted.web.server import NOT_DONE_YET
        return NOT_DONE_YET

    def _set_resource(self, wrapped_resource):
        self._wrapped_resource = wrapped_resource

    def _cbChild(self, _ignored, request):
        request.render(getChildForRequest(
            self._wrapped_resource, request))

    def _ebChild(self, reason, request):
        request.processingFailed(reason)
        return reason


def _build_resource_deferred():
    """
    We need to wait for the connection pool to connect before we can create the
    Resource, so this returns a Deferred that will later be wrapped in a
    DeferredResource object.
    """

    connection_string = app_settings.get_connection_string()
    connection_pool = DictRowConnectionPool(
        None, connection_string, min=app_settings.API_MIN_CONNECTIONS,
        detector=DeadConnectionDetector())
    log.info("Connecting to database %s..." % (connection_string,))
    import sys
    sys.stderr.write("XXX%s\n" % (connection_pool,))

    d = connection_pool.start()
    d.addCallback(Root)
    return d


def billing_api_resource():
    """
    Create and return a go.billing.api.Root resource for use with twistd.
    """
    connection_string = app_settings.get_connection_string()
    connection_pool = DictRowConnectionPool(
        None, connection_string, min=app_settings.API_MIN_CONNECTIONS)
    connection_pool.start()
    return Root(connection_pool)
    # return DeferredResource(_build_resource_deferred())
