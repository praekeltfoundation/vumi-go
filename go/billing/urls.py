from django.conf.urls import patterns, url
from go.billing import views

urlpatterns = patterns(
    '',
    url(
        r'^statement/(?P<statement_id>[\d]+)', views.statement_view,
        name='html_statement')
)
