from django.db import models

# Create your models here.
class Conversation(models.Model):
    """A conversation with an audience"""
    user = models.ForeignKey('auth.User')
    subject = models.CharField('Conversation Name', max_length=255)
    message = models.TextField('Message')
    start_date = models.DateField()
    start_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    group = models.ForeignKey('base.ContactGroup', null=True)
    # TODO: specify which transports to send & receive on
    # transports = models.ManyToManyField('transport.Type')
    
    def previewcontact_set(self):
        if not self.group:
            return []
        return self.group.contact_set.all()[:5]
    
    class Meta:
        ordering = ['-updated_at']
        get_latest_by = 'updated_at'

    def __unicode__(self):
        return self.subject
