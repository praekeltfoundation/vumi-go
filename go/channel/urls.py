from django.conf.urls import patterns, url
from go.channel import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^new/$', views.new_channel, name='new_channel'),
    url(r'^(?P<channel_key>[^/]+)/(?P<path_suffix>.*)$',
        views.channel, name='channel'),
)
