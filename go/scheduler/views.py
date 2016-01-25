from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.generic import ListView
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectMixin

from go.scheduler.models import Task, PendingTask


class SchedulerListView(ListView):
    paginate_by = 12
    context_object_name = 'tasks'
    template = 'scheduler/task_list.html'

    def get_queryset(self):
        return Task.objects.filter(
            account_id=self.request.user_api.user_account_key
            ).order_by('-scheduled_for')


class SchedulerDelete(SingleObjectMixin, View):
    model = Task
    url = reverse_lazy('scheduler:tasks')

    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        task = self.get_object()

        if task.status != Task.STATUS_PENDING:
            raise PermissionDenied
        if task.account_id != self.request.user_api.user_account_key:
            raise PermissionDenied

        task.status = Task.STATUS_CANCELLED
        task.save()

        PendingTask.objects.get(task=task).delete()

        return HttpResponseRedirect(self.url)


class SchedulerCreatePendingTask(SingleObjectMixin, View):
    model = Task
    url = reverse_lazy('scheduler:tasks')

    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        task = self.get_object()

        if task.status != Task.STATUS_CANCELLED:
            raise PermissionDenied
        if task.account_id != self.request.user_api.user_account_key:
            raise PermissionDenied

        PendingTask.objects.create(
            task=task, scheduled_for=task.scheduled_for)
        task.status = Task.STATUS_PENDING
        task.save()

        return HttpResponseRedirect(self.url)
