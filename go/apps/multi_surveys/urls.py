from django.conf.urls.defaults import patterns, url
from go.apps.multi_surveys import views

urlpatterns = patterns('',
    url(r'^new/$', views.new, name='new'),
    url(r'^(?P<conversation_key>\w+)/$', views.show, name='show'),
    url(r'^(?P<conversation_key>\w+)/surveys/$',
        views.surveys, name='surveys'),
    url(r'^(?P<conversation_key>\w+)/surveys/new/$',
        views.new_survey, name='new_survey'),
    url(r'^(?P<conversation_key>\w+)/surveys/(?P<poll_name>.+)/$',
        views.survey, name='survey'),
    url(r'^(?P<conversation_key>\w+)/people/$', views.people, name='people'),
    url(r'^(?P<conversation_key>\w+)/start/$', views.start, name='start'),
    url(r'^(?P<conversation_key>\w+)/end/$', views.end, name='end'),
)
