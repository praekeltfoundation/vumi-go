import datetime
from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse
    from django.template import defaultfilters
    from django.test.client import Client
    from django.conf import settings
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.scheduler.models import Task, PendingTask
    from go.scheduler.views import SchedulerListView


class TestSchedulerBase(object):
    def create_task(self, label, account_id=None, delta=7):
        now = datetime.datetime.now()
        scheduled_time = now + datetime.timedelta(days=delta)
        if account_id is None:
            account_id = self.user_helper.account_key
        return Task.objects.create(
            account_id=account_id, label=label, scheduled_for=scheduled_time)

    def assert_contains_task(self, response, task):
        self.assertContains(response, task.label)
        self.assertContains(response, task.get_task_type_display())
        self.assertContains(response, task.get_status_display())
        formatted_date = defaultfilters.date(
            task.scheduled_for, settings.DATETIME_FORMAT)
        self.assertContains(response, formatted_date)
        timezone = defaultfilters.date(
            task.scheduled_for, 'T')
        self.assertContains(response, timezone)
        time_remaining = defaultfilters.timeuntil(task.scheduled_for)
        self.assertContains(response, time_remaining)


class TestSchedulerListView(GoDjangoTestCase, TestSchedulerBase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def test_no_tasks(self):
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertContains(r, '>Scheduled Tasks</a>')
        self.assertContains(r, '>No scheduled tasks<')

    def test_login_required(self):
        self.client.logout()
        r = self.client.get(reverse('scheduler:tasks'))
        expected_url = "%s?next=%s" % (
            reverse('auth_login'), reverse('scheduler:tasks'))
        self.assertRedirects(r, expected_url)

    def test_single_task(self):
        task = self.create_task('Test task')
        r = self.client.get(reverse('scheduler:tasks'))
        self.assert_contains_task(r, task)

    def test_multiple_pages(self):
        '''If there are more tasks than fit in a single page view, then only
        the tasks that fit should be shown, with navigation to go to next and
        previous pages. Tasks are sorted in reverse chronological order.'''
        tasks = []
        for i in range(SchedulerListView.paginate_by + 1):
            task = self.create_task('Test task %d' % i)
            tasks.append(task)

        tasks.sort(key=lambda t: t.scheduled_for, reverse=True)
        excluded_task = tasks.pop()

        r = self.client.get(reverse('scheduler:tasks'))
        for task in tasks:
            self.assert_contains_task(r, task)
        self.assertNotContains(r, excluded_task.label)
        self.assertContains(r, '&larr;</a>')
        self.assertContains(r, '&rarr;</a>')

        r = self.client.get(reverse('scheduler:tasks'), {'page': 2})
        self.assert_contains_task(r, excluded_task)

    def test_task_different_user(self):
        user2 = self.vumi_helper.make_django_user(email='user2@domain.com')
        task = self.create_task('Test task', account_id=user2.account_key)
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertNotContains(r, task.label)

    def test_scheduled_tasks_in_header(self):
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertContains(r, '>Scheduled Tasks</a></li>')

    def test_scheduler_list_cancel_button(self):
        self.create_task('Test task')
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertContains(
            r, '<button class="btn btn-danger">Cancel</button>', html=True)

    def test_scheduler_list_disabled_cancel_button(self):
        task = self.create_task('Test task')
        task.status = Task.STATUS_COMPLETED
        task.save()

        r = self.client.get(reverse('scheduler:tasks'))
        self.assertContains(
            r, '<button class="btn btn-danger" disabled>Cancel</button>',
            html=True)

    def test_scheduler_list_reactivate_button(self):
        task = self.create_task('Test task')
        task.status = Task.STATUS_CANCELLED
        task.save()

        r = self.client.get(reverse('scheduler:tasks'))
        self.assertContains(
            r, '<button class="btn btn-primary">Reactivate</button>',
            html=True)


class TestSchedulerDeleteView(GoDjangoTestCase, TestSchedulerBase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def test_login_required(self):
        self.client.logout()
        r = self.client.post(
            reverse('scheduler:delete_task', kwargs={'pk': 1}))
        expected_url = "%s?next=%s" % (
            reverse('auth_login'),
            reverse('scheduler:delete_task', kwargs={'pk': 1}))
        self.assertRedirects(r, expected_url)

    def test_csrf_protect(self):
        user = self.user_helper.get_django_user()
        client = Client(
            username=user.email,
            password=user.password,
            enforce_csrf_checks=True)
        task = self.create_task('Test task')
        r = client.post(
            reverse('scheduler:delete_task', kwargs={'pk': task.pk}))
        self.assertContains(r, 'CSRF verification failed.', status_code=403)

    def test_delete_task(self):
        task = self.create_task('Test task')
        pending = PendingTask.objects.get(task=task)
        self.assertEqual(pending.task, task)

        r = self.client.post(
            reverse('scheduler:delete_task', kwargs={'pk': task.pk}))

        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.status, Task.STATUS_CANCELLED)

        pending_tasks = PendingTask.objects.filter(task=task)
        self.assertEqual(len(pending_tasks), 0)

        self.assertRedirects(r, reverse('scheduler:tasks'))

    def test_delete_task_not_pending(self):
        task_cancelled = self.create_task('Test task')
        task_cancelled.status = Task.STATUS_CANCELLED
        task_cancelled.save()

        r = self.client.post(
            reverse('scheduler:delete_task', kwargs={'pk': task_cancelled.pk}))
        self.assertContains(r, "403 Forbidden", status_code=403)

        task_completed = self.create_task('Test task')
        task_completed.status = Task.STATUS_COMPLETED
        task_completed.save()

        r = self.client.post(
            reverse('scheduler:delete_task', kwargs={'pk': task_completed.pk}))
        self.assertContains(r, "403 Forbidden", status_code=403)

    def test_delete_task_wrong_user(self):
        user2 = self.vumi_helper.make_django_user(email='user2@domain.com')
        task = self.create_task('Test task', account_id=user2.account_key)
        r = self.client.post(
            reverse('scheduler:delete_task', kwargs={'pk': task.pk}))
        self.assertContains(r, "403 Forbidden", status_code=403)


class TestSchedulerCreatePendingView(GoDjangoTestCase, TestSchedulerBase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def test_login_required(self):
        self.client.logout()
        r = self.client.post(
            reverse('scheduler:reactivate_task', kwargs={'pk': 1}))
        expected_url = "%s?next=%s" % (
            reverse('auth_login'),
            reverse('scheduler:reactivate_task', kwargs={'pk': 1}))
        self.assertRedirects(r, expected_url)

    def test_csrf_protect(self):
        user = self.user_helper.get_django_user()
        client = Client(
            username=user.email,
            password=user.password,
            enforce_csrf_checks=True)
        task = self.create_task('Test task')
        r = client.post(
            reverse('scheduler:reactivate_task', kwargs={'pk': task.pk}))
        self.assertContains(r, 'CSRF verification failed.', status_code=403)

    def test_reactivate_task(self):
        task = self.create_task('Test task')
        PendingTask.objects.get(task=task).delete()
        task.status = Task.STATUS_CANCELLED
        task.save()

        r = self.client.post(
            reverse('scheduler:reactivate_task', kwargs={'pk': task.pk}))

        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.status, Task.STATUS_PENDING)

        pending_task = PendingTask.objects.get(task=task)
        self.assertEqual(pending_task.task, task)

        self.assertRedirects(r, reverse('scheduler:tasks'))

    def test_reactivate_task_not_cancelled(self):
        task_pending = self.create_task('Test task')
        task_pending.status = Task.STATUS_PENDING
        task_pending.save()

        r = self.client.post(reverse(
            'scheduler:reactivate_task', kwargs={'pk': task_pending.pk}))
        self.assertContains(r, "403 Forbidden", status_code=403)

        task_completed = self.create_task('Test task')
        task_completed.status = Task.STATUS_COMPLETED
        task_completed.save()

        r = self.client.post(reverse(
            'scheduler:reactivate_task', kwargs={'pk': task_completed.pk}))
        self.assertContains(r, "403 Forbidden", status_code=403)

    def test_reactivate_task_wrong_user(self):
        user2 = self.vumi_helper.make_django_user(email='user2@domain.com')
        task = self.create_task('Test task', account_id=user2.account_key)
        r = self.client.post(
            reverse('scheduler:reactivate_task', kwargs={'pk': task.pk}))
        self.assertContains(r, "403 Forbidden", status_code=403)
