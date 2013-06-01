from django.conf.urls.defaults import patterns, url

from registration.backends.default.urls import urlpatterns as authpatterns
from registration.views import register

from go.account.forms import RegistrationForm
from go.account import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^register/$', register, {
        'backend': 'registration.backends.default.DefaultBackend',
        'form_class': RegistrationForm,
        },
        name='registration_register'),
    url(r'^details/$', views.details, name='auth_details'),
)
urlpatterns += authpatterns
