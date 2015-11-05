from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase
    from go.scheduler.models import (PendingTask, Task)


class TestPendingTask(GoDjangoTestCase):
    def test_unicode(self):
        task = Task(account_id="user-1", label="Send messages")
        pending = PendingTask(task=task)
        self.assertEqual(
            unicode(pending),
            u"[Pending] Send messages (conversation-action for user-1)")


class TestTask(GoDjangoTestCase):
    def test_unicode(self):
        task = Task(account_id="user-1", label="Send messages")
        self.assertEqual(
            unicode(task),
            u"Send messages (conversation-action for user-1)")
