from django.conf import settings
from django.db import models


class AirtimeVoucherPool(models.Model):
    """Represents an Airtime Voucher pool"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    pool_name = models.CharField(max_length=100)
    ext_pool_name = models.CharField(
        max_length=255, unique=True,
        help_text="Pool name in the Airtime Voucher Service")

    date_created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.pool_name


class UniqueCodePool(models.Model):
    """Represents an Unique Code pool"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    pool_name = models.CharField(max_length=100)
    ext_pool_name = models.CharField(
        max_length=255, unique=True,
        help_text="Pool name in the Unique Code Service")

    date_created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.pool_name
