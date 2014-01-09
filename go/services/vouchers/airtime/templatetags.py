import logging

from go.services.vouchers.service import VoucherServiceError
from go.services.vouchers.airtime.service import VoucherService

logger = logging.getLogger(__name__)

simple_tags = ['airtime_vouchers_total']


def airtime_vouchers_total(voucher_pool):
    """Return the total number of airtime vouchers in the given `voucher_pool`"""
    voucher_service = VoucherService()
    try:
        return voucher_service.total_vouchers(voucher_pool)
    except VoucherServiceError as error:
        logger.exception(error)
    return 0
