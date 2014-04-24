from django.conf.urls import patterns, url

from go.api import views

urlpatterns = patterns('',
    url(r'^v1/go/api$', views.go_api_proxy, name='go_api_proxy'),
)
