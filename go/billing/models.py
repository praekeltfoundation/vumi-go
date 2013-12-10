from decimal import Decimal, Context, Inexact, Underflow

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

import go.billing.settings as app_settings


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

    account = models.ForeignKey(Account, blank=True, null=True)
    tag_pool = models.ForeignKey(TagPool)
    message_direction = models.CharField(max_length=20,
                                         choices=DIRECTION_CHOICES)

    message_cost = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0.0'),
        help_text=_("The base message cost in cents."))

    markup_percent = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.0'),
        help_text=_("The markup percentage. e.g. 20.0 for twenty percent"))

    @property
    def resulting_price(self):
        """Return the resulting price in cents"""
        markup_amount = (self.message_cost
                         * self.markup_percent / Decimal('100.0'))

        return self.message_cost + markup_amount

    @property
    def credit_cost(self):
        """Return the calculated cost in credits"""
        credit_cost = self.resulting_price * Decimal(
            app_settings.CREDIT_CONVERSION_FACTOR)

        return credit_cost.quantize(Decimal('.000001'),
                                    context=Context(
                                        traps=[Inexact, Underflow]))

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
    message_cost = models.IntegerField(blank=True, null=True)
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
