from django.conf.urls import patterns, url
from go.router import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^new/$', views.new_router, name='new_router'),
    url(r'^(?P<router_key>[^/]+)/(?P<path_suffix>.*)$',
        views.router, name='router'),
)
