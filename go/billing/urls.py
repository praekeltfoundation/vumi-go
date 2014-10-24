from django.conf.urls import patterns, url
from go.billing import views

urlpatterns = patterns(
    '',
    url(
        r'^(?P<statement_id>[\d]+)', views.statement_view,
        name='pdf_statement')
)
