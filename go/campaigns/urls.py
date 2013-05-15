from django.conf.urls.defaults import patterns, url
from go.campaigns import views

urlpatterns = patterns('',
    url(r'^details/$', views.details, name='details'),
    url(r'^message/(?P<campaign_key>\w+)/$', views.message, name='message'),
    url(r'^message/(?P<campaign_key>\w+)/bulk/$', views.message_bulk,
        name='message_bulk'),
    url(r'^message/(?P<campaign_key>\w+)/conversation/$',
        views.message_conversation, name='message_conversation'),
    url(r'^contacts/(?P<campaign_key>\w+)/', views.contacts, name='contacts'),
    url(r'^summary/$', views.todo, name='summary'),
)
