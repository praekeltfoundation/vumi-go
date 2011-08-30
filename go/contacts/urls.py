from django.conf.urls.defaults import patterns, url
from go.contacts import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^groups/$', views.groups, name='groups'),
    url(r'^people/$', views.people, name='people'),
    # url(r'^new/', views.new, name='new'),
    # url(r'^(?P<conversation_pk>\d+)/people/', views.participants,
    #     name='participants'),
    # url(r'^(?P<conversation_pk>\d+)/send/', views.send, name='send'),
    # url(r'^(?P<conversation_pk>\d+)/start/', views.start, name='start'),
    # url(r'^(?P<conversation_pk>\d+)/', views.show, name='show'),
)
