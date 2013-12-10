import logging

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger(__name__)


class VoucherPool(models.Model):
    """Refers to a pool of Airtime Vouchers or Unique Codes.

    The actual airtime vouchers/unique codes are stored in an external system.
    """

    POOL_TYPE_AIRTIME = 'Airtime'
    POOL_TYPE_UNIQUE_CODE = 'Unique code'
    POOL_TYPE_CHOICES = (
        (POOL_TYPE_AIRTIME, POOL_TYPE_AIRTIME),
        (POOL_TYPE_UNIQUE_CODE, POOL_TYPE_UNIQUE_CODE),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    pool_name = models.CharField(max_length=100)
    ext_pool_name = models.CharField(
        max_length=255, unique=True,
        help_text=_("Pool name in the external system"))

    pool_type = models.CharField(max_length=20, choices=POOL_TYPE_CHOICES)
    date_created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.pool_name


class BulkImport(models.Model):
    """Keep a log of voucher import attempts"""

    STATUS_PENDING = 'Pending'
    STATUS_COMPLETED = 'Completed'
    STATUS_FAILED = 'Failed'
    STATUS_CHOICES = (
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_COMPLETED, STATUS_COMPLETED),
        (STATUS_FAILED, STATUS_FAILED),
    )

    voucher_pool = models.ForeignKey(VoucherPool, related_name='imports')
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=STATUS_PENDING)

    date_imported = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.filename
