import datetime

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from celery.task import task, group

    from go.scheduler.models import PendingTask, Task
    from go.base.utils import (
        get_conversation_view_definition, vumi_api)


@task()
def perform_task(pending_id):
    """ Perform a task. """
    pending = PendingTask.objects.get(id=pending_id)
    task = pending.task
    if task.task_type == Task.TYPE_CONVERSATION_ACTION:
        perform_conversation_action(task)
    pending.delete()


def perform_conversation_action(task):
    """
    Perform a conversation action. ``task_data`` must have the following
    fields:

    user_account_key - The key of the user account.
    conversation_key - The key for the conversation.
    action_name - The name of the action to be performed.
    action_kwargs - A dictionary representing the keyword arguments for an
                    action.
    """
    user_api = vumi_api().get_user_api(
        task.task_data['user_account_key'], cleanup_api=True)
    conv = user_api.get_wrapped_conversation(
        task.task_data['conversation_key'])
    view_def = get_conversation_view_definition(
        conv.conversation_type, conv=conv)
    action = view_def.get_action(
        task.task_data['action_name'])
    action.perform_action(task.task_data['action_kwargs'])
    user_api.close()


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
