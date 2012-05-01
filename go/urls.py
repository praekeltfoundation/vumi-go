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

    # django default auth
    url(r'^accounts/login/$', 'django.contrib.auth.views.login',
        name='login'),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout',
        name='logout'),

    # simple todo view for stuff that's not completed yet
    url(r'^todo/.*$', 'go.base.views.todo', name='todo'),

    # vumi go!
    url(r'^$', RedirectView.as_view(url='/conversations/', permanent=False,
                                    query_string=True), name='home'),
    url(r'^conversations/',
        include('go.conversation.urls', namespace='conversations')),
    url(r'^app/',
        include('go.apps.urls')),
    url(r'^contacts/', include('go.contacts.urls', namespace='contacts')),
    url(r'^', include('vxpolls.urls')),
)

urlpatterns += patterns('django.contrib.flatpages.views',
    url(r'^credits/$', 'flatpage', {'url': '/credits/'}, name='credits'),
    url(r'^help/$', 'flatpage', {'url': '/help/'}, name='help'),
)

# HAProxy health check
urlpatterns += patterns('',
    url(r'^health/$', health, name='health'),
)
