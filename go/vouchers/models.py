import logging

from django.conf import settings
from django.db import models

from go.vouchers.services import (
    AirtimeVoucherService,
    AirtimeVoucherServiceError)


logger = logging.getLogger(__name__)


class AirtimeVoucherPool(models.Model):
    """Represents an Airtime Voucher pool"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    pool_name = models.CharField(max_length=100)
    ext_pool_name = models.CharField(
        max_length=255, unique=True,
        help_text="Pool name in the Airtime Voucher Service")

    date_created = models.DateTimeField(auto_now_add=True)

    @property
    def total_vouchers(self):
        airtime_voucher_service = AirtimeVoucherService()
        try:
            return airtime_voucher_service.total_vouchers(self.ext_pool_name)
        except AirtimeVoucherServiceError as error:
            logger.exception(error)
        return 0

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
