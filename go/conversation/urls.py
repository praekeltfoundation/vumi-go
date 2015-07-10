from django.conf.urls import patterns, url
from go.conversation import views

urlpatterns = patterns(
    '',
    url(r'^$', views.index, name='index'),
    url(r'^new/$', views.new_conversation, name='new_conversation'),
    url(r'^(?P<conversation_key>\w+)/action/(?P<action_name>.*)$',
        views.conversation_action, name='conversation_action'),
    url(r'^(?P<conversation_key>\w+)/(?P<path_suffix>.*)$',
        views.conversation, name='conversation'),
)
