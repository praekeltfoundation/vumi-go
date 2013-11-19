import json

from requests.exceptions import HTTPError

from go.dashboard import DiamondashApiClient


class FakeDiamondashApiClient(DiamondashApiClient):
    def __init__(self):
        self.requests = []
        self.response = None

    def get_requests(self):
        return self.requests

    def set_error_response(self, message):
        self.response = HTTPError(json.dumps({
            'success': False,
            'message': message
        }))

    def set_response(self, response):
        self.response = response

    def request(self, method, url, data):
        self.requests.append({
            'method': method,
            'url': url,
            'data': data,
        })

        if isinstance(self.response, Exception):
            raise self.response

        return self.response
