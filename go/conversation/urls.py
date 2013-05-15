from django.conf.urls.defaults import patterns, url
from go.conversation import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^new/(?P<conversation_type>.*)/$',
        views.new_conversation, name='new_conversation'),
    url(r'^(?P<conversation_key>\w+)/(?P<path_suffix>.*)$',
        views.conversation, name='conversation'),
)
