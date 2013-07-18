from django.conf.urls.defaults import patterns, url
from go.wizard import views

urlpatterns = patterns(
    '',
    url(r'^create/$', views.create, name='create'),
    url(r'^create/(?P<conversation_key>\w+)/$', views.create, name='create'),
    url(r'^contacts/(?P<conversation_key>\w+)/', views.contacts,
        name='contacts'),
    url(r'^pricing/$', views.pricing, name='pricing'),
)
