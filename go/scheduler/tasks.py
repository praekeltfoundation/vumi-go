import datetime

from celery.task import task, group

from go.scheduler.models import PendingTask


@task()
def perform_task(pending_id):
    """ Perform a task. """
    pending = PendingTask.objects.get(id=pending_id)
    # TODO: perform task
    pending.delete()


@task()
def poll_tasks():
    """ Poll for tasks that are due and process them.
    """
    now = datetime.datetime.utcnow()
    ready_tasks = PendingTask.objects.filter(scheduled_for__lte=now)

    task_list = []
    for pending in ready_tasks:
        task_list.append(perform_task.s(pending.pk))

    return group(task_list)()
