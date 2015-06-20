import json
import decimal
import datetime

from StringIO import StringIO

# For psycopg2, if we're using it.
try:
    from psycopg2cffi import compat
except ImportError:
    pass
else:
    compat.register()

import psycopg2
import psycopg2.extras

from twisted.internet import defer
from twisted.web import server
from twisted.web.test import test_web

from txpostgres import txpostgres, reconnection

from go.config import billing_quantization_exponent


class BillingError(Exception):
    """Raised when an error occurs during billing."""


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder to handle ``Decimal`` and ``datetime`` values"""

    class EncodeError(Exception):
        """Raised when an error occurs during encoding"""

    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            context = decimal.Context()
            value = obj.quantize(billing_quantization_exponent(),
                                 context=context)

            if (context.flags[decimal.Inexact]
                    and value == decimal.Decimal('0.0')):
                raise self.EncodeError("Decimal quantization resulted in 0")

            return float(value)

        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return json.JSONEncoder.default(self, obj)


class JSONDecoder(json.JSONDecoder):
    """JSONDecoder to handle ``float`` values"""

    class DecodeError(Exception):
        """Raised when an error occurs during decoding"""

    def __init__(self, *args, **kwargs):
        kwargs['parse_float'] = self.parse_float_str
        super(JSONDecoder, self).__init__(*args, **kwargs)

    def parse_float_str(self, num_str):
        context = decimal.Context()
        value = decimal.Decimal(num_str).quantize(
            billing_quantization_exponent(), context=context)

        if (context.flags[decimal.Inexact]
                and value == decimal.Decimal('0.0')):
            raise self.DecodeError("Decimal quantization resulted in 0")

        return value


def real_dict_connect(*args, **kwargs):
    kwargs['connection_factory'] = psycopg2.extras.RealDictConnection
    return psycopg2.connect(*args, **kwargs)


class DictRowConnection(txpostgres.Connection):
    """Extend the txpostgres ``Connection`` and override the
    ``cursorFactory``

    """

    connectionFactory = staticmethod(real_dict_connect)

    def __init__(self, *args, **kw):
        super(DictRowConnection, self).__init__(*args, **kw)
        if self.detector is None:
            self.detector = reconnection.DeadConnectionDetector()

    def connect(self, *args, **kw):
        d = super(DictRowConnection, self).connect(*args, **kw)
        # We set self.detector in __init__ if there isn't one already.
        d.addErrback(self.detector.checkForDeadConnection)
        return d

    @property
    def closed(self):
        """Return ``True`` if the underlying connection is closed
        ``False`` otherwise

        """
        if self._connection:
            return self._connection.closed
        return True


class DictRowConnectionPool(txpostgres.ConnectionPool):
    """Extend the txpostgres ``ConnectionPool`` and override the
    ``connectionFactory``

    """

    connectionFactory = DictRowConnection

    @property
    def closed(self):
        """Return ``True`` all the connections are closed
        ``False`` otherwise

        """
        return all(c.closed for c in self.connections)


class DummyRequest(test_web.DummyRequest):
    def __init__(self, method, url, args=None, content=None, headers=None):
        test_web.DummyRequest.__init__(self, url.split('/'))
        self.method = method
        if content:
            self.content = StringIO(json.dumps(content, cls=JSONEncoder))
        else:
            self.content = None
        self.headers.update(headers or {})

        args = args or {}
        for k, v in args.items():
            self.addArg(k, v)

    def value(self):
        return "".join(self.written)


class DummySite(server.Site):
    def get(self, url, args=None, headers=None):
        return self._request('GET', url, args, None, headers)

    def post(self, url, args=None, content=None, headers=None):
        return self._request('POST', url, args, content, headers)

    def _request(self, method, url, args, content, headers):
        request = DummyRequest(method, url, args, content, headers)
        resource = self.getResourceFor(request)
        result = resource.render(request)
        return self._resolve_result(request, result)

    def _resolve_result(self, request, result):
        if isinstance(result, str):
            request.write(result)
            request.finish()
            return defer.succeed(request)
        elif result is server.NOT_DONE_YET:
            if request.finished:
                return defer.succeed(request)
            else:
                return request.notifyFinish().addCallback(lambda _: request)
        else:
            raise ValueError("Unexpected return value: %r" % (result,))

    @property
    def connection_pool(self):
        return self.resource._connection_pool
