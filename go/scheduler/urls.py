from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from go.scheduler.views import (
    SchedulerCreatePendingTask, SchedulerDelete, SchedulerListView)


urlpatterns = patterns(
    '',
    url(r'^$', login_required(SchedulerListView.as_view()), name='tasks'),
    url(
        r'^(?P<pk>\d+)/delete$', login_required(SchedulerDelete.as_view()),
        name='delete_task'),
    url(
        r'^(?P<pk>\d+)/reactivate$',
        login_required(SchedulerCreatePendingTask.as_view()),
        name='reactivate_task'),
)
