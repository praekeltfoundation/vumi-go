import json

from go.dashboard.client import DiamondashApiError, DiamondashApiClient


class FakeDiamondashApiClient(DiamondashApiClient):
    def __init__(self):
        self.requests = []
        self.set_response()

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

        self._response = DiamondashApiError(code, data)

    def set_raw_response(self, content="", code=200):
        self._response = {
            'code': code,
            'content': content,
        }

    def set_response(self, data=None, code=200):
        self.set_raw_response(code=code, content=json.dumps({
            'success': True,
            'data': data,
        }))

    def get_requests(self):
        return self.requests

    def raw_request(self, method, url, content=""):
        self.requests.append({
            'method': method,
            'url': url,
            'content': content,
        })

        return self.response

    def request(self, method, url, data=None):
        self.requests.append({
            'method': method,
            'url': url,
            'data': data,
        })

        resp_data = json.loads(self.response['content'])
        return resp_data['data']
