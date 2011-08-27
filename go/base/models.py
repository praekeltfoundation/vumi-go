from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User

def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User)

class UserProfile(models.Model):
    """A profile for a user"""
    user = models.OneToOneField('auth.User')
    
    def get_display_name(self):
        return '%s %s' % (self.user.first_name, self.user.last_name)

    def __unicode__(self):
        return u"UserProfile for %s" % self.user
    

class ContactGroup(models.Model):
    """A group of contacts"""
    user = models.ForeignKey('auth.User')
    name = models.CharField(blank=False, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        get_latest_by = 'updated_at'
    
    def __unicode__(self):
        return self.name
    
