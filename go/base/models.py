from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User,
    dispatch_uid='go.base.models.create_user_profile')


class UserProfile(models.Model):
    """A profile for a user"""
    user = models.OneToOneField('auth.User')

    def __unicode__(self):
        return u' '.join([self.user.first_name, self.user.last_name])

