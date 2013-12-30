import logging

from django import template

from go.services.voucher_utils import VoucherServiceError

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag
def total_vouchers(service_type, voucher_pool):
    """Return the total number of vouchers in the given `voucher_pool`"""
    try:
        if service_type == 'airtime':
            from go.services.airtime.utils import VoucherService
            voucher_service = VoucherService()
            return voucher_service.total_vouchers(voucher_pool)

    except VoucherServiceError as error:
        logger.exception(error)
    return 0
