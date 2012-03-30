from django.conf.urls.defaults import patterns, include, url
from afropinions.webapp.surveys import views

urlpatterns = patterns('',
    url(r'^new/$', views.new, name='new'),
    url(r'^(?P<conversation_pk>\d+)/$', views.show, name='show'),
    url(r'^(?P<conversation_pk>\d+)/contents/$', views.contents, name='contents'),
    url(r'^(?P<conversation_pk>\d+)/people/$', views.people, name='people'),
    url(r'^(?P<conversation_pk>\d+)/start/$', views.start, name='start'),
    url(r'^(?P<conversation_pk>\d+)/end/$', views.end, name='end'),
)