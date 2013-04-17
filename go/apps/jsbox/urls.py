from django.conf.urls.defaults import patterns, url

from go.apps.jsbox.views import (
    JsboxConversationViews, cross_domain_xhr, post_commit)

urlpatterns = JsboxConversationViews().get_urlpatterns()

urlpatterns += patterns('',
    url(r'^cross-domain-xhr/$', cross_domain_xhr),
    url(r'^(?P<account_key>\w+)/(?P<conversation_key>\w+)/post-commit/$',
        post_commit, name='post_commit'),
)
