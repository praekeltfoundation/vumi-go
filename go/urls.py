from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.http import HttpResponse
from django.views.generic import RedirectView

from go.base.views import cross_domain_xhr


admin.autodiscover()


def health(request):
    return HttpResponse('')

urlpatterns = patterns(
    '',
    # django admin site
    url(r'^grappelli/', include('grappelli.urls')),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    # simple todo view for stuff that's not completed yet
    url(r'^todo/.*$', 'go.base.views.todo', name='todo'),

    # confirmation tokens
    url(r'^t/', include('go.token.urls')),

    # proxy for cross-domain xhrs
    url(r'^cross-domain-xhr/', cross_domain_xhr, name='cross_domain_xhr'),

    # vumi go!
    url(r'^$', RedirectView.as_view(url='/conversations/', permanent=False,
                                    query_string=True), name='home'),
    url(r'^conversations/',
        include('go.conversation.urls', namespace='conversations')),
    url(r'^routers/', include('go.router.urls', namespace='routers')),
    url(r'^channels/', include('go.channel.urls', namespace='channels'))
    url(r'^contacts/', include('go.contacts.urls', namespace='contacts')),
    url(r'^account/', include('go.account.urls', namespace='account')),
    url(r'^accounts/', include('registration.backends.default.urls')),
    url(r'^billing/', include('go.billing.urls', namespace='billing')),

    url(r'^routing/$', 'go.routing.views.routing', name='routing'),

    # proxy API calls
    url(r'^api/', include('go.api.urls', namespace='api')),

    # proxy diamondash calls
    url(r'^diamondash/', include('go.dashboard.urls', namespace='dashboard')),
)

urlpatterns += patterns(
    'django.contrib.flatpages.views',
    url(r'^credits/$', 'flatpage', {'url': '/credits/'}, name='credits'),
    url(r'^help/$', 'flatpage', {'url': '/help/'}, name='help'),
)

urlpatterns += patterns(
    'loginas.views',
    url(r"^login/user/(?P<user_id>.+)/$", "user_login",
        name="loginas-user-login"),
)

# HAProxy health check
urlpatterns += patterns(
    '',
    url(r'^health/$', health, name='health'),
)
