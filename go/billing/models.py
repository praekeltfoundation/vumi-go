from decimal import Decimal

from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _
from django.conf import settings


import go.billing.settings as app_settings
from go.base.models import UserProfile


class TagPool(models.Model):
    """Tag pool definition"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __unicode__(self):
        return self.name


class Account(models.Model):
    """Represents a user account"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    account_number = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    credit_balance = models.DecimalField(max_digits=20, decimal_places=6,
                                         default=Decimal('0.0'))

    alert_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.0'),
        help_text=_("Low-credits notification will be sent when the "
                    "credit balance reaches the alert threshold percentage"))

    alert_credit_balance = models.DecimalField(
        max_digits=20, decimal_places=6, default=Decimal('0.0'))

    def __unicode__(self):
        return u"{0} ({1})".format(self.account_number, self.user.email)


def create_billing_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(user=instance.user,
                               account_number=instance.user_account)


post_save.connect(create_billing_account, sender=UserProfile,
    dispatch_uid='go.billing.models.create_billing_account')


class MessageCost(models.Model):
    """Specifies the cost of a single message.

    The cost of a message is defined in terms of the tag pool and the message
    direction. The cost can optionally be overridden on a per account basis.

    """

    DIRECTION_INBOUND = 'Inbound'
    DIRECTION_OUTBOUND = 'Outbound'
    DIRECTION_CHOICES = (
        (DIRECTION_INBOUND, DIRECTION_INBOUND),
        (DIRECTION_OUTBOUND, DIRECTION_OUTBOUND),
    )

    @classmethod
    def apply_markup_and_convert_to_credits(cls, cost, markup_percent,
                                            context=None):
        """
        Takes a cost (in cents), applies markup and converts the resulting
        amount to credits.
        """
        cost = cost + (cost * markup_percent / Decimal('100.0'))
        credits = cost * Decimal(app_settings.CREDIT_CONVERSION_FACTOR)
        return credits.quantize(app_settings.QUANTIZATION_EXPONENT,
                                context=context)

    @classmethod
    def calculate_message_credit_cost(cls, message_cost, markup_percent,
                                      context=None):
        """
        Return the cost per message (in credits).
        """
        return cls.apply_markup_and_convert_to_credits(
            message_cost, markup_percent, context=context)

    @classmethod
    def calculate_session_credit_cost(cls, session_cost, markup_percent,
                                      context=None):
        """
        Return the cost per session (in credits).
        """
        return cls.apply_markup_and_convert_to_credits(
            session_cost, markup_percent, context=context)

    @classmethod
    def calculate_credit_cost(cls, message_cost, markup_percent,
                              session_cost, session_created, context=None):
        """
        Return the total cost for both the message and the session, if any,
        in credits.
        """
        base_cost = message_cost
        if session_created:
            base_cost += session_cost
        return cls.apply_markup_and_convert_to_credits(
            base_cost, markup_percent, context=context)

    class Meta:
        unique_together = [
            ['account', 'tag_pool', 'message_direction'],
        ]

        index_together = [
            ['account', 'tag_pool', 'message_direction'],
        ]

    account = models.ForeignKey(
        Account, blank=True, null=True, db_index=True,
        help_text=_("The account this cost entry is for. If null, this entry"
                    " is a fallback for all accounts."))

    tag_pool = models.ForeignKey(
        TagPool, blank=True, null=True, db_index=True,
        help_text=_("The tag pool this cost entry is for. If null, this entry"
                    " is a fallback for all tag pools."))

    message_direction = models.CharField(
        max_length=20, choices=DIRECTION_CHOICES, db_index=True,
        help_text=_("This cost entry applies only to messages being sent or"
                    " received in the given direction. 'Inbound' is for"
                    " MO messages. 'Outbound' is for MT messages."))

    message_cost = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0.0'),
        help_text=_("The base message cost in cents."))

    session_cost = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0.0'),
        help_text=_("The base cost per session in cents."))

    markup_percent = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.0'),
        help_text=_("The markup percentage. e.g. 20.0 for twenty percent"))

    @property
    def message_credit_cost(self):
        """Return the calculated cost per message (in credits)."""
        return self.calculate_message_credit_cost(
            self.message_cost, self.markup_percent)

    @property
    def session_credit_cost(self):
        """Return the calculated cost per session (in credits)."""
        return self.calculate_session_credit_cost(
            self.session_cost, self.markup_percent)

    def __unicode__(self):
        return u"%s (%s)" % (self.tag_pool, self.message_direction)


class Transaction(models.Model):
    """Represents a credit transaction"""

    STATUS_PENDING = 'Pending'
    STATUS_COMPLETED = 'Completed'
    STATUS_FAILED = 'Failed'
    STATUS_REVERSED = 'Reversed'
    STATUS_CHOICES = (
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_COMPLETED, STATUS_COMPLETED),
        (STATUS_FAILED, STATUS_FAILED),
        (STATUS_REVERSED, STATUS_REVERSED),
    )

    account_number = models.CharField(max_length=100)
    tag_pool_name = models.CharField(max_length=100, blank=True)
    tag_name = models.CharField(max_length=100, blank=True)
    message_direction = models.CharField(max_length=20, blank=True)

    message_id = models.CharField(
        max_length=64, null=True, blank=True,
        help_text=_("Vumi message identifier for the message being"
                    " billed (or null if there is no associated message)"))

    message_cost = models.DecimalField(
        null=True,
        max_digits=10, decimal_places=3, default=Decimal('0.0'),
        help_text=_("The message cost (in cents) used to calculate"
                    " credit_amount."))

    session_created = models.NullBooleanField(blank=True, null=True)

    session_cost = models.DecimalField(
        null=True,
        max_digits=10, decimal_places=3, default=Decimal('0.0'),
        help_text=_("The session cost (in cents) used to calculate"
                    " credit_amount."))

    markup_percent = models.DecimalField(max_digits=10, decimal_places=2,
                                         blank=True, null=True)

    credit_factor = models.DecimalField(max_digits=10, decimal_places=2,
                                        blank=True, null=True)

    credit_amount = models.DecimalField(max_digits=20, decimal_places=6,
                                        default=Decimal('0.0'))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=STATUS_PENDING)

    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return unicode(self.pk)


class Statement(models.Model):
    """Account statement for a period of time"""

    TYPE_MONTHLY = 'Monthly'
    TYPE_CHOICES = (
        (TYPE_MONTHLY, TYPE_MONTHLY),
    )

    account = models.ForeignKey(Account)
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    from_date = models.DateField()
    to_date = models.DateField()
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"%s for %s" % (self.title, self.account)


class LineItem(models.Model):
    """A line item of a statement"""

    statement = models.ForeignKey(Statement)
    tag_pool_name = models.CharField(max_length=100, blank=True, default='')
    tag_name = models.CharField(max_length=100, blank=True, default='')
    message_direction = models.CharField(max_length=20, blank=True,
                                         default='')

    total_cost = models.IntegerField(default=0)

    def __unicode__(self):
        return u"%s line item" % (self.statement.title,)
