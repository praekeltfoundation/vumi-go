import datetime
from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse
    from django.template import defaultfilters
    from django.conf import settings
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.scheduler.models import Task
    from go.scheduler.views import SchedulerListView

class TestSchedulerListView(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def create_task(self, label, account_id=None, delta=7):
        now = datetime.datetime.now()
        scheduled_time = now + datetime.timedelta(days=delta)
        if account_id is None:
            account_id = self.user_helper.account_key
        return Task.objects.create(
            account_id=account_id, label=label, scheduled_for=scheduled_time)

    def test_no_tasks(self):
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertContains(r, '>Scheduled Tasks</a>')
        self.assertContains(r, '>No scheduled tasks<')

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

    def test_single_task(self):
        task = self.create_task('Test task') 
        r = self.client.get(reverse('scheduler:tasks'))
        self.assert_contains_task(r, task)

    def test_multiple_pages(self):
        tasks = []
        for i in range(SchedulerListView.paginate_by + 1):
            task = self.create_task('Test task %d' % i)
            tasks.append(task)

        r = self.client.get(reverse('scheduler:tasks'))
        excluded_task = tasks.pop()
        for task in tasks:
            self.assert_contains_task(r, task)
        self.assertNotContains(r, excluded_task.label)

        self.assertContains(r, '&larr;</a>')
        self.assertContains(r, '&rarr;</a>')

    def test_task_past(self):
        task = self.create_task('Test task', delta=-7)
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertNotContains(r, task.label)

    def test_task_different_user(self):
        user2 = self.vumi_helper.make_django_user(email='user2@domain.com')
        task = self.create_task('Test task', account_id=user2.account_key)
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertNotContains(r, task.label)

    def test_scheduled_tasks_in_header(self):
        r = self.client.get(reverse('scheduler:tasks'))
        self.assertContains(r, '>Scheduled Tasks</a></li>')
        