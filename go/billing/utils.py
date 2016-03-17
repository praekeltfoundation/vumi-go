import json
import decimal
import datetime

from StringIO import StringIO

from twisted.internet import defer
from twisted.web import server
from twisted.web.test import test_web

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


class DummyRequest(test_web.DummyRequest):
    def __init__(self, method, url, args=None, content=None, headers=None):
        test_web.DummyRequest.__init__(self, url.split('/'))
        self.method = method
        if content:
            self.content = StringIO(json.dumps(content, cls=JSONEncoder))
        else:
            self.content = None
        headers = headers or {}
        for header, value in headers.items():
            self.requestHeaders.addRawHeader(header, value)

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
