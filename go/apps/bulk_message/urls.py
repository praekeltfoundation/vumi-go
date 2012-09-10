from django.conf.urls.defaults import patterns
from go.apps.bulk_message.views import BulkSendConversationViews

urlpatterns = patterns('', *BulkSendConversationViews().urls())
