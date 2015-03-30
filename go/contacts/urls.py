from django.conf.urls import patterns, url
from go.contacts import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^groups/$', views.groups, name='groups', kwargs={'type': 'static'}),
    url(r'^groups/(?P<type>[\w ]+)/$', views.groups, name='groups_type'),
    url(r'^group/(?P<group_key>[\w ]+)/$', views.group, name='group'),
    url(r'^people/$', views.people, name='people'),
    url(r'^people/new/$', views.new_person, name='new_person'),
    url(r'^people/(?P<person_key>\w+)/$', views.person, name='person'),
)
