from go.base.tests.utils import FakeResponse


class FakeDiamondashResponse(FakeResponse):
    def __init__(self, data=None, code=200):
        data = self.make_response_data(data)
        super(FakeDiamondashResponse, self).__init__(data=data, code=code)

    def make_response_data(self, data=None):
        return {
            'success': True,
            'data': data
        }


class FakeDiamondashErrorResponse(FakeResponse):
    def __init__(self, message, code):
        data = self.make_response_data(message)
        super(FakeDiamondashErrorResponse, self).__init__(data=data, code=code)

    def make_response_data(self, message):
        return {
            'success': False,
            'message': message
        }
