import datetime

import mock

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase
    from go.scheduler import tasks
    from go.scheduler.models import Task


class TestPerformTask(GoDjangoTestCase):
    def test_perform_task(self):
        now = datetime.datetime.utcnow()
        task = Task.objects.create(
            account_id="user-1", label="Task 1", scheduled_for=now)
        [pending] = task.pendingtask_set.all()
        tasks.perform_task(pending.pk)
        self.assertEqual(list(task.pendingtask_set.all()), [])


class TestPollTasks(GoDjangoTestCase):

    @mock.patch('go.scheduler.tasks.perform_task.s',
                new_callable=mock.MagicMock)
    def test_no_pending_tasks(self, s):
        tasks.poll_tasks()
        s.assert_not_called()

    @mock.patch('go.scheduler.tasks.perform_task.s',
                new_callable=mock.MagicMock)
    def test_some_pending_task(self, s):
        now = datetime.datetime.utcnow()
        t1 = Task.objects.create(
            account_id="user-1", label="Task 1", scheduled_for=now)
        t2 = Task.objects.create(
            account_id="user-2", label="Task 2", scheduled_for=now)
        Task.objects.create(
            account_id="user-2", label="Task 3", scheduled_for=now +
            datetime.timedelta(days=30))

        tasks.poll_tasks()
        s.assertEqual(s.call_args_list, [
            mock.call(t1.pk),
            mock.call(t2.pk),
        ])
