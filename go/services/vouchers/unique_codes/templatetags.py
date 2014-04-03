import logging

from go.services.vouchers.service import VoucherServiceError
from go.services.vouchers.unique_codes.service import UniqueCodeService

logger = logging.getLogger(__name__)

simple_tags = ['unique_codes_total']


def unique_codes_total(unique_code_pool):
    """Return the total number of unique codes in the given
    `unique_code_pool`.
    """
    voucher_service = UniqueCodeService()
    try:
        return voucher_service.total_unique_codes(unique_code_pool)
    except VoucherServiceError as error:
        logger.exception(error)
    return 0
