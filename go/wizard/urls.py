from django.conf.urls.defaults import patterns, url
from go.wizard import views

urlpatterns = patterns(
    '',
    url(r'^create/$', views.create, name='create'),
    url(r'^create/(?P<conversation_key>\w+)/$', views.create, name='create'),
    url(r'^edit/(?P<conversation_key>\w+)/$', views.edit,
        name='edit'),
    url(r'^edit/(?P<conversation_key>\w+)/bulk/$', views.edit_bulk_message,
        name='edit_bulk_message'),
    url(r'^edit/(?P<conversation_key>\w+)/survey/$', views.edit_survey,
        name='edit_survey'),
    url(r'^contacts/(?P<conversation_key>\w+)/', views.contacts,
        name='contacts'),
    url(r'^pricing/$', views.pricing, name='pricing'),
)
