from django.conf.urls.defaults import patterns, url
from go.conversation_tmp import views

urlpatterns = patterns(
    '',
    url(r'^details/$', views.details, name='details'),
    url(r'^details/(?P<campaign_key>\w+)/$', views.details, name='details'),
    # TODO: message is probably not a good name for these views, considering
    # that you get incoming messages as well.
    url(r'^message/(?P<campaign_key>\w+)/$', views.message, name='message'),
    url(r'^message/(?P<campaign_key>\w+)/bulk/$', views.message_bulk,
        name='message_bulk_message'),
    url(r'^message/(?P<campaign_key>\w+)/survey/$',
        views.message_survey,
        name='message_survey'),
    url(r'^contacts/(?P<campaign_key>\w+)/', views.contacts, name='contacts'),
    url(r'^preview/(?P<campaign_key>\w+)/$', views.preview, name='preview'),
    url(r'^incoming/(?P<campaign_key>\w+)/$', views.incoming_list,
        name='incoming_list'),
    url(r'^incoming/(?P<campaign_key>\w+)/(?P<contact_key>\w+)/$',
        views.incoming_detail, name='incoming_detail'),
    url(r'^pricing/$', views.pricing, name='pricing'),
    url(r'^routing/$', views.routing, name='routing'),
)
