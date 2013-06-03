from django.conf.urls.defaults import patterns, url

from registration.backends.default.urls import urlpatterns as authpatterns
from registration.views import register

from go.account.forms import RegistrationForm
from go.account import views

urlpatterns = patterns('',
    url(r'^register/$', register, {
        'backend': 'registration.backends.default.DefaultBackend',
        'form_class': RegistrationForm,
        },
        name='registration_register'),
    url(r'^details/$', views.details, name='auth_details'),
    url(r'^users/$', 'go.base.views.todo', name='auth_user_list'),
    url(r'^users/(?P<user_id>\d+)/$', 'go.base.views.todo',
        name='auth_user_detail'),
)
urlpatterns += authpatterns
