from django.conf.urls.defaults import patterns, url

from go.apps.jsbox.views import (
    JsboxConversationViews, cross_domain_xhr, jsbox_logs)

urlpatterns = JsboxConversationViews().get_urlpatterns()

urlpatterns += patterns('',
    url(r'^cross-domain-xhr/$', cross_domain_xhr, name="cross_domain_xhr"),
    url(r'^jslogs/$', jsbox_logs, name="jsbox_logs"),
)
