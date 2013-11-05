import json
import decimal
import datetime

from StringIO import StringIO

import psycopg2
import psycopg2.extras

from twisted.internet import defer
from twisted.web import server
from twisted.web.test import test_web

from txpostgres import txpostgres


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder to handle ``Decimal`` and ``datetime`` values"""

    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj.quantize(decimal.Decimal('.01')))
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return json.JSONEncoder.default(self, obj)


def parse_float(num_str):
    return decimal.Decimal(num_str).quantize(decimal.Decimal('.01'))


def real_dict_connect(*args, **kwargs):
    kwargs['connection_factory'] = psycopg2.extras.RealDictConnection
    return psycopg2.connect(*args, **kwargs)


class DictRowConnection(txpostgres.Connection):
    """Extend the txpostgres ``Connection`` and override the
    ``cursorFactory``

    """

    connectionFactory = staticmethod(real_dict_connect)

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
