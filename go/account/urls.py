from django.conf.urls.defaults import patterns, url
from go.account import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
)
