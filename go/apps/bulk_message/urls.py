from django.conf.urls.defaults import patterns, url
from go.apps.bulk_message import views

urlpatterns = patterns('',
    url(r'^new/', views.new, name='new'),
    url(r'^(?P<conversation_key>\w+)/people/', views.people, name='people'),
    url(r'^(?P<conversation_key>\w+)/send/', views.send, name='send'),
    url(r'^(?P<conversation_key>\w+)/end/', views.end, name='end'),
    url(r'^(?P<conversation_key>\w+)/', views.show, name='show'),
)
