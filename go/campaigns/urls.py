from django.conf.urls.defaults import patterns, url
from go.campaigns import views

urlpatterns = patterns('',
    # url(r'^$', views.index, name='index'), # perhaps the dashboard?
    url(r'^details/$', views.details, name='details'),
    url(r'^details/$', views.details, name='details'),
    url(r'^message/(?P<campaign_key>[\w ]+)/$', views.message, name='message'),
    url(r'^message/(?P<campaign_key>[\w ]+)/bulk/$', views.message_bulk,
        name='message_bulk'),
    url(r'^message/(?P<campaign_key>[\w ]+)/conversation/$',
        views.message_conversation, name='message_conversation'),

#     url(r'^recipients/$', views.create, name='create'),
#     url(r'^summary/$', views.create, name='create'),
)
