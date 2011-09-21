from django.conf.urls.defaults import patterns, url
from go.contacts import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^groups/$', views.groups, name='groups'),
    url(r'^groups/(?P<group_pk>\d+)/$', views.group, name='group'),
    url(r'^people/$', views.people, name='people'),
    url(r'^people/(?P<person_pk>\d+)/$', views.person, name='person'),
)
