from django.conf.urls.defaults import patterns, url, include

urlpatterns = patterns('',
    url(r'^survey/',
        include('go.apps.surveys.urls', namespace='survey')),
    url(r'^bulk_message/',
        include('go.apps.bulk_message.urls', namespace='bulk_message')),
)
