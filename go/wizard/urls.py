from django.conf.urls import patterns, url
from go.wizard import views

urlpatterns = patterns(
    '',
    url(r'^create/$', views.WizardCreateView.as_view(), name='create'),
    url(r'^contacts/(?P<conversation_key>\w+)/', views.contacts,
        name='contacts'),
    url(r'^pricing/$', views.pricing, name='pricing'),
)
