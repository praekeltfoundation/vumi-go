from django.conf.urls.defaults import patterns, include, url
from django.contrib import admin
from django.http import HttpResponse
from django.views.generic import RedirectView


admin.autodiscover()

def health(request):
    return HttpResponse('')

urlpatterns = patterns('',
    # django admin site
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    # simple todo view for stuff that's not completed yet
    url(r'^todo/.*$', 'go.base.views.todo', name='todo'),
    url(r'^t/task/$', 'go.base.views.token_task', name='token_task'),
    url(r'^t/(?P<token>\w+)/$', 'go.base.views.token', name='token'),

    # vumi go!
    url(r'^$', RedirectView.as_view(url='/conversations/', permanent=False,
                                    query_string=True), name='home'),
    url(r'^conversations/',
        include('go.conversation.urls', namespace='conversations')),
    url(r'^conversation-tmp/', include('go.conversation_tmp.urls', 
        namespace='conversations_tmp')),
    url(r'^app/', include('go.apps.urls')),
    url(r'^contacts/', include('go.contacts.urls', namespace='contacts')),
    url(r'^account/', include('go.account.urls', namespace='account')),
    url(r'^accounts/', include('registration.backends.default.urls')),
)

urlpatterns += patterns('django.contrib.flatpages.views',
    url(r'^credits/$', 'flatpage', {'url': '/credits/'}, name='credits'),
    url(r'^help/$', 'flatpage', {'url': '/help/'}, name='help'),
)

# HAProxy health check
urlpatterns += patterns('',
    url(r'^health/$', health, name='health'),
)
