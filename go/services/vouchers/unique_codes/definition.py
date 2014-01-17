from go.services.definition import ServiceDefinitionBase
from go.services.vouchers.unique_codes.service import UniqueCodeService


class ServiceDefinition(ServiceDefinitionBase):

    service_type = u"unique_codes"
    service_display_name = u"Unique codes"

    voucher_service = UniqueCodeService()
