from go.base.utils import vumi_api_for_user


class VumiUserApiMiddleware(object):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated():
            request.user_api = vumi_api_for_user(request.user)
