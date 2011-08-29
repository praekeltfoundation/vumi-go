from django.db import models
from go.base.models import Contact


class ConversationManager(models.Manager):
    def recent(self, limit=6, pad=True, padding=None):
        """
        Returns the most recent conversations, number is specified by `limit`.
        If `pad` is set to True then it will return a list of example `limit`
        entries, if there are less than `limit` entries available in the
        database it will create empty entries in the list with value `padding`
        which defaults to `None`.
        """
        conversations = self.get_query_set().order_by('updated_at')
        recent_conversations = conversations[:limit]
        if pad:
            nr_of_results = recent_conversations.count()
            if nr_of_results < limit:
                filler = [padding] * (limit - nr_of_results)
                recent_conversations = list(recent_conversations)
                recent_conversations.extend(filler)
        return recent_conversations


class Conversation(models.Model):
    """A conversation with an audience"""
    user = models.ForeignKey('auth.User')
    subject = models.CharField('Conversation Name', max_length=255)
    message = models.TextField('Message')
    start_date = models.DateField()
    start_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    groups = models.ManyToManyField('base.ContactGroup')
    previewcontacts = models.ManyToManyField('base.Contact')

    objects = ConversationManager()

    def participants(self):
        return Contact.objects.filter(groups__in=self.groups.all())

    class Meta:
        ordering = ['-updated_at']
        get_latest_by = 'updated_at'

    def __unicode__(self):
        return self.subject
