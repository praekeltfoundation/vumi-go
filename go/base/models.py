from django.db import connection, models
from django.db.models.signals import post_save, post_syncdb
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin)
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.conf import settings

from go.base.utils import vumi_api, vumi_api_for_user


class GoUserManager(BaseUserManager):
    def _create_user(self, email, password, **kw):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, **kw)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None):
        return self._create_user(
            email, password,
            is_superuser=False, is_staff=False, is_active=True)

    def create_superuser(self, email, password):
        return self._create_user(
            email, password,
            is_superuser=True, is_staff=True, is_active=True)


class GoUser(AbstractBaseUser, PermissionsMixin):
    objects = GoUserManager()

    email = models.EmailField(max_length=254, unique=True)
    first_name = models.CharField(max_length=254)
    last_name = models.CharField(max_length=254)
    date_joined = models.DateTimeField(default=timezone.now)

    is_staff = models.BooleanField('staff status', default=False,
        help_text='Designates whether the user can log into this admin '
                    'site.')
    is_active = models.BooleanField('active', default=True,
        help_text='Designates whether this user should be treated as '
                    'active. Unselect this instead of deleting accounts.')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def get_full_name(self):
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        return self.first_name

    def get_profile(self):
        return self.userprofile


class UserOrganisation(models.Model):
    """A group of users belong to an organisations"""
    name = models.CharField(max_length=128)

    def __unicode__(self):
        return self.name


class UserProfile(models.Model):
    """A profile for a user"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL)
    user_account = models.CharField(max_length=100)
    organisation = models.ForeignKey(UserOrganisation, blank=True, null=True)
    is_admin = models.BooleanField(default=False)

    def __unicode__(self):
        return u"%s's profile" % self.user.email

    def get_user_account(self, api):
        return api.account_store.get_user(self.user_account)


def create_user_profile(sender, instance, created, **kwargs):
    api = vumi_api()
    try:
        if created:
            username = instance.get_username()
            account = api.account_store.new_user(unicode(username))
            UserProfile.objects.create(user=instance, user_account=account.key)
        user_api = vumi_api_for_user(instance, api)
        # Enable search for the contact & group stores
        user_api.contact_store.contacts.enable_search()
        user_api.contact_store.groups.enable_search()
    finally:
        api.cleanup()


post_save.connect(create_user_profile, sender=GoUser,
    dispatch_uid='go.base.models.create_user_profile')


def create_permissions_for_tests(*args, **kw):
    from django.contrib.auth.models import ContentType, Permission
    if 'auth_permission' not in connection.introspection.table_names():
        return
    for model in ('gouser', 'user', 'permission', 'group'):
            ct, _ = ContentType.objects.get_or_create(
                model=model, app_label='auth')
            for perm_name in ('add', 'change', 'delete'):
                codename = '%s_%s' % (model, perm_name)
                name = 'Can %s %s' % (perm_name, model)
                Permission.objects.get_or_create(
                    content_type=ct, codename=codename, name=name)


def fix_auth_post_syncdb():
    """Disconnects post_syncdb signals so that syncdb doesn't attempt to call
       create_permissions or create_superuser before South migrations have had
       chance to run. Connects a new post_syncdb hook that creates permissions
       during tests.
       """
    # ensure signals have had a chance to be connected
    __import__('django.contrib.auth.management')
    post_syncdb.disconnect(
        dispatch_uid="django.contrib.auth.management.create_permissions")
    post_syncdb.disconnect(
        dispatch_uid="django.contrib.auth.management.create_superuser")
    post_syncdb.connect(
        create_permissions_for_tests,
        dispatch_uid="go.base.models.create_permissions_for_tests")

fix_auth_post_syncdb()
