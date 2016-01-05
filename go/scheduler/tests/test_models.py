import datetime
import re

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.db.utils import IntegrityError
    from go.base.tests.helpers import GoDjangoTestCase
    from go.scheduler.models import (PendingTask, Task)


def mk_task(create=False, **kw):
    kw.setdefault('account_id', "user-1")
    kw.setdefault('label', "Send messages")
    kw.setdefault('scheduled_for', datetime.datetime(2015, 1, 1, 7, 0))
    if create:
        return Task.objects.create(**kw)
    return Task(**kw)


class TestPendingTask(GoDjangoTestCase):

    def assert_not_null_constraint_violated(self, pending, field):
        self.assertRaisesRegexp(
            IntegrityError, re.escape(field),
            pending.save)

    def test_validate_task_not_null(self):
        pending = PendingTask(
            scheduled_for=datetime.datetime(2015, 1, 1, 7, 0))
        self.assert_not_null_constraint_violated(pending, 'task_id')

    def test_validate_scheduled_for_not_null(self):
        task = mk_task()
        task.save()
        pending = PendingTask(task=task)
        self.assert_not_null_constraint_violated(pending, 'scheduled_for')

    def test_started_timestamp_null(self):
        task = mk_task()
        task.save()
        pending = PendingTask(
            task=task, scheduled_for=datetime.datetime(2015, 1, 1, 7, 0))
        pending.save()
        self.assertEqual(pending.started_timestamp, None)

    def test_unicode(self):
        task = Task(account_id="user-1", label="Send messages")
        pending = PendingTask(task=task)
        self.assertEqual(
            unicode(pending),
            u"[Pending] Send messages (conversation-action for user-1)")


class TestTask(GoDjangoTestCase):

    def assert_not_null_constraint_violated(self, task, field):
        self.assertRaisesRegexp(
            IntegrityError, re.escape(field),
            task.save)

    def test_default_task_type(self):
        task = Task()
        self.assertEqual(task.task_type, Task.TYPE_CONVERSATION_ACTION)

    def test_default_status(self):
        task = Task()
        self.assertEqual(task.status, Task.STATUS_PENDING)

    def test_validate_account_id_not_null(self):
        task = mk_task(account_id=None)
        self.assert_not_null_constraint_violated(task, 'account_id')

    def test_validate_label_not_null(self):
        task = mk_task(label=None)
        self.assert_not_null_constraint_violated(task, 'label')

    def test_validate_scheduled_for_not_null(self):
        task = mk_task(scheduled_for=None)
        self.assert_not_null_constraint_violated(task, 'scheduled_for')

    def test_created_auto_populated(self):
        task = mk_task()
        self.assertEqual(task.created, None)
        task.save()
        self.assertNotEqual(task.created, None)

    def test_task_data_dict(self):
        task = mk_task(task_data={"param": "ram"})
        task.save()
        task = Task.objects.get(id=task.id)
        self.assertEqual(task.task_data, {"param": "ram"})

    def test_task_data_none(self):
        task = mk_task(task_data=None)
        task.save()
        task = Task.objects.get(id=task.id)
        self.assertEqual(task.task_data, None)

    def test_pending_created(self):
        task = mk_task(create=True)
        pending = PendingTask.objects.get(task=task)
        self.assertEqual(pending.task, task)
        self.assertEqual(pending.scheduled_for, task.scheduled_for)

    def test_unicode(self):
        task = Task(account_id="user-1", label="Send messages")
        self.assertEqual(
            unicode(task),
            u"Send messages (conversation-action for user-1)")
