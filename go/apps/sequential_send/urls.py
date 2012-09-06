from django.conf.urls.defaults import patterns, url
from go.apps.sequential_send import views

urlpatterns = patterns('',
    url(r'^new/$', views.new, name='new'),
    url(r'^(?P<conversation_key>\w+)/$', views.show, name='show'),
    url(r'^(?P<conversation_key>\w+)/people/$', views.people, name='people'),
    url(r'^(?P<conversation_key>\w+)/start/$', views.start, name='start'),
    url(r'^(?P<conversation_key>\w+)/end/$', views.end, name='end'),
)
