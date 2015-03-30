from django.conf.urls import patterns, url

from go.account import views

urlpatterns = patterns('',
    url(r'^register/$', views.GoRegistrationView,
        name='registration_register'),
    url(r'^details/$', views.details, name='details'),
    url(r'^users/$', views.user_list, name='user_list'),
    url(r'^users/create/$', views.user_detail, name='user_create'),
    url(r'^users/(?P<user_id>\d+)/$', views.user_detail,
        name='user_detail'),
    url(r'^billing/$', views.billing, name='billing'),
)
