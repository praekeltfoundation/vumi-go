from django.conf.urls import patterns, url

from go.dashboard import views

urlpatterns = patterns('',
    url(r'^api/.*$', views.diamondash_api_proxy, name='diamondash_api_proxy'))
