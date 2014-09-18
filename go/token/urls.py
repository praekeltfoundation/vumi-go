from django.conf.urls import patterns, url

from go.token import views


urlpatterns = patterns('',
    url(r'^task/$', views.token_task, name='token_task'),
    url(r'^(?P<token>\w+)/$', views.token, name='token'),
)
