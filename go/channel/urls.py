from django.conf.urls.defaults import patterns, url
from go.channel import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^new/$', views.new_channel, name='new_channel'),
)
