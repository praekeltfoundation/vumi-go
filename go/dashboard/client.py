import json

import requests
from django.conf import settings


class DiamondashApiError(Exception):
    """
    Raised when we something goes wrong while trying to interact with
    diamondash api.
    """
    def __init__(self, code, content):
        super(DiamondashApiError, self).__init__("%s: %s" % (code, content))
        self.code = code
        self.content = content


class DiamondashApiClient(object):
    def make_api_url(self, path):
        return '/'.join(
            p.strip('/')
            for p in [settings.DIAMONDASH_API_URL, path])

    def get_api_auth(self):
        username = getattr(settings, 'DIAMONDASH_API_USERNAME', None)
        password = getattr(settings, 'DIAMONDASH_API_PASSWORD', None)

        if username is not None and password is not None:
            auth = (username, password)
        else:
            auth = None

        return auth

    def raw_request(self, method, path, content=""):
        resp = requests.request(
            method,
            data=content,
            url=self.make_api_url(path),
            auth=self.get_api_auth())

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            raise DiamondashApiError(
                resp.status_code, resp.content)

        return {
            'code': resp.status_code,
            'content': resp.content
        }

    def request(self, method, path, data=None):
        resp = self.raw_request(method, path, content=json.dumps(data))
        resp_data = json.loads(resp['content'])
        return resp_data['data']

    def replace_dashboard(self, config):
        return self.request('put', 'dashboards', config)


def get_diamondash_api():
    return DiamondashApiClient()
