import json

import requests
from django.conf import settings


class DiamondashApiError(Exception):
    """
    Raised when we something goes wrong while trying to interact with
    diamondash api.
    """


class DiamondashApiClient(object):
    def make_api_url(self, path):
        return '/'.join(
            p.strip('/')
            for p in [settings.DIAMONDASH_API_URL, path])

    def raw_request(self, method, path, content=""):
        resp = requests.request(method, self.make_api_url(path), data=content)

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise DiamondashApiError(
                "%s: %s" % (e, resp.content))

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
