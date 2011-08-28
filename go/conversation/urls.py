from django.conf.urls.defaults import patterns, include, url
from go.conversation import views

urlpatterns = patterns('',
    url(r'^new/', views.new, name='new'),
    url(r'^(?P<conversation_pk>\d+)/people/', views.participants, name='participants'),
    url(r'^(?P<conversation_pk>\d+)/send/', views.send, name='send'),
)
