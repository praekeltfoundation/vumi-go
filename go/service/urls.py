from django.conf.urls.defaults import patterns, url

from go.service import views

urlpatterns = patterns(
    '',
    url(r'^$', views.index, name='index'),
    url(r'^new/$', views.new_service, name='new_service'),
    url(r'^(?P<service_key>[^/]+)/(?P<path_suffix>.*)$',
        views.service, name='service'),
)
