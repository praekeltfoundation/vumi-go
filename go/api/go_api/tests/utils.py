from mock import Mock, patch


class MockRpc(object):
    def __init__(self):
        self.response = self.set_response()
        self.request = None

        self.rpc_patcher = patch('go.api.go_api.client.rpc')
        self.mock_rpc = self.rpc_patcher.start()
        self.mock_rpc.side_effect = self.stubbed_rpc

    def tearDown(self):
        self.rpc_patcher.stop()

    def stubbed_rpc(self, session_id, method, params, id=None):
        self.request = {
            'session_id': session_id,
            'method': method,
            'params': params,
            'id': id,
        }

        return self.response

    @staticmethod
    def make_response_data(result={}, id=None):
        return {
            'id': id,
            'jsonrpc': '2.0',
            'result': result,
        }

    def set_response(self, result={}, id=None):
        response = Mock()
        response.status_code = 200
        response.json = self.make_response_data(result, id)
        self.response = response

    def set_rpc_error_response(self, error, id=None):
        response = Mock()
        response.status_code = 200

        data = self.make_response_data(result=None, id=id)
        data.error = error
        response.json = data

        self.response = response

    def set_error_response(self, code, text):
        response = Mock()
        response.status_code = code
        response.text = text
        self.response = response
