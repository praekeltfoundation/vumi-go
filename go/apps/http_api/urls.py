from go.apps.http_api.views import HttpApiConversationViews

urlpatterns = HttpApiConversationViews().get_urlpatterns()
