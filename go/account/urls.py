from django.conf.urls.defaults import patterns, url

#from registration.backends.default.urls import urlpatterns as authpatterns
from registration.views import register

from go.account.forms import RegistrationForm
from go.account import views

urlpatterns = patterns('',
    url(r'^register/$', register, {
        'backend': 'registration.backends.default.DefaultBackend',
        'form_class': RegistrationForm,
        },
        name='registration_register'),
    url(r'^details/$', views.details, name='details'),
    url(r'^users/$', views.user_list, name='user_list'),
    url(r'^users/create/$', views.user_detail, name='user_create'),
    url(r'^users/(?P<user_id>\d+)/$', views.user_detail,
        name='user_detail'),
    url(r'^billing/$', views.billing, name='billing'),
)
#urlpatterns += authpatterns
