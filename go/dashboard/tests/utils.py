import json

from go.dashboard.client import DiamondashApiError, DiamondashApiClient


class FakeDiamondashApiClient(DiamondashApiClient):
    def __init__(self):
        self.requests = []
        self._response = None

    @property
    def response(self):
        if isinstance(self._response, Exception):
            raise self._response

        return self._response

    def set_error_response(self, code, message):
        data = json.dumps({
            'success': False,
            'message': message
        })

        self._response = DiamondashApiError("(%s) %s" % (code, data))

    def set_response(self, response):
        self._response = response

    def get_requests(self):
        return self.requests

    def request(self, method, url, data):
        self.requests.append({
            'method': method,
            'url': url,
            'data': data,
        })

        return self.response

    def raw_request(self, method, url, content=""):
        self.requests.append({
            'method': method,
            'url': url,
            'content': content,
        })

        return self.response
