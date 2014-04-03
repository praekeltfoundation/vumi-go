from django.conf.urls.defaults import patterns, url

from go.services import views

urlpatterns = patterns(
    '',
    url(r'^$', views.index, name='index'),
    url(r'^(?P<service_type>\w+)$', views.service,
        {'path_suffix': None}, name='service_index'),
    url(r'^(?P<service_type>\w+)/(?P<path_suffix>.+)$',
        views.service, name='service'),
)
