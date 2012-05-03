from django.conf.urls.defaults import patterns, url
from go.conversation import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
)
