from django.conf.urls.defaults import patterns
from go.apps.opt_out.views import OptOutConversationViews

urlpatterns = patterns('', *OptOutConversationViews().urls())
