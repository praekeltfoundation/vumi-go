from django.conf.urls.defaults import patterns, url
from go.contacts import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^groups/$', views.groups, name='groups'),
    # TODO: Is the group_name regex sane?
    url(r'^groups/(?P<group_key>\w+)/$', views.group, name='group'),
    url(r'^people/$', views.people, name='people'),
    url(r'^people/new/$', views.new_person, name='new_person'),
    url(r'^people/(?P<person_key>.+)/$', views.person, name='person'),
)
