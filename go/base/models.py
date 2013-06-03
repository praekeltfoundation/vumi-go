from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.conf import settings

from vumi.persist.riak_manager import RiakManager
from go.vumitools.account import AccountStore
from go.base.utils import vumi_api_for_user


def get_account_store():
    return AccountStore(RiakManager.from_config(
            settings.VUMI_API_CONFIG['riak_manager']))


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        account = get_account_store().new_user(unicode(instance.username))
        UserProfile.objects.create(user=instance, user_account=account.key)
    user_api = vumi_api_for_user(instance)
    # Enable search for the contact & group stores
    user_api.contact_store.contacts.enable_search()
    user_api.contact_store.groups.enable_search()


post_save.connect(create_user_profile, sender=User,
    dispatch_uid='go.base.models.create_user_profile')


class UserOrganisation(models.Model):
    """A group of users belong to an organisations"""
    name = models.CharField(max_length=128)

    def __unicode__(self):
        return self.name


class UserProfile(models.Model):
    """A profile for a user"""
    user = models.OneToOneField('auth.User')
    user_account = models.CharField(max_length=100)
    organisation = models.ForeignKey(UserOrganisation, blank=True, null=True)

    def __unicode__(self):
        return u' '.join([self.user.first_name, self.user.last_name])

    def get_user_account(self):
        return get_account_store().get_user(self.user_account)
