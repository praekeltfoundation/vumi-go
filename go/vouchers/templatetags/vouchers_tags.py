import logging

from django import template

from go.vouchers.models import VoucherPool
from go.vouchers.services import AirtimeVoucherService, VoucherServiceError

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag
def total_vouchers(voucher_pool):
    """Return the total number of vouchers in the given `voucher_pool`"""
    try:
        if voucher_pool.pool_type == VoucherPool.POOL_TYPE_AIRTIME:
            voucher_service = AirtimeVoucherService()
            return voucher_service.total_vouchers(voucher_pool)
    except VoucherServiceError as error:
        logger.exception(error)
    return 0
