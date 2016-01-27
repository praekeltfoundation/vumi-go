from django.conf.urls import patterns, url
from go.scheduler.views import SchedulerListView


urlpatterns = patterns(
    '',
    url(r'^$', SchedulerListView.as_view(), name='tasks'),
)
