""" Models for go.scheduler. """

from django.db import models
from django.utils.translation import ugettext_lazy as _


class PendingTask(models.Model):
    """ Tasks waiting to execute. """

    task = models.ForeignKey(
        'Task',
        blank=False, null=False,
        help_text=_("The full task record."))

    scheduled_for = models.DateTimeField(
        blank=False, null=False,
        help_text=_("When the task is or was scheduled to run."))

    def __unicode__(self):
        return u"[Pending] %s (%s for %s)" % (
            self.task.label, self.task.task_type, self.task.account_id)


class TaskManager(models.Manager):
    def create(self, **kw):
        task = super(TaskManager, self).create(**kw)
        PendingTask.objects.create(
            task=task, scheduled_for=task.scheduled_for)
        return task


class Task(models.Model):
    """ Record of a scheduled task. """

    objects = TaskManager()

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    TYPE_CONVERSATION_ACTION = 'conversation-action'
    TYPE_CHOICES = (
        (TYPE_CONVERSATION_ACTION, "Conversation Action"),
    )

    account_id = models.CharField(
        max_length=255, blank=False, null=False,
        help_text=_("The account that owns the task."))

    label = models.CharField(
        max_length=255, blank=False, null=False,
        help_text=_("Human readable description of the task."))

    task_type = models.CharField(
        max_length=32, choices=TYPE_CHOICES, default=TYPE_CONVERSATION_ACTION,
        help_text=_("The type of the task."))

    task_data = models.TextField(
        help_text=_("The task details as JSON data."))

    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING,
        help_text=_("The status of this task. One of pending, "
                    "completed, or cancelled."))

    scheduled_for = models.DateTimeField(
        blank=False, null=False,
        help_text=_("When the task is or was scheduled to run."))

    created = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When this task was created."))

    def __unicode__(self):
        return u"%s (%s for %s)" % (
            self.label, self.task_type, self.account_id)
