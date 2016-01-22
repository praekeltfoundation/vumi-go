import datetime
from django.views.generic import ListView

from go.scheduler.models import Task


class SchedulerListView(ListView):
    paginate_by = 12
    context_object_name = 'tasks'
    template = 'scheduler/task_list.html'

    def get_queryset(self):
        now = datetime.datetime.utcnow()
        return Task.objects.filter(
            account_id=self.request.user_api.user_account_key
            ).order_by('-scheduled_for')
