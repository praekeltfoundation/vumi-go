from django.conf.urls.defaults import patterns, url
from go.campaigns import views

urlpatterns = patterns('',
    # url(r'^$', views.index, name='index'), # perhaps the dashboard?
    url(r'^new/$', views.new, name='new'),
#     url(r'^message/$', views.create, name='create'),
#     url(r'^conversation/$', views.create, name='create'),
#     url(r'^recipients/$', views.create, name='create'),
#     url(r'^summary/$', views.create, name='create'),
)
