from go.services.definition import ServiceDefinitionBase
from go.services.airtime.utils import VoucherService


class ServiceDefinition(ServiceDefinitionBase):

    service_type = u"airtime"
    service_display_name = u"Airtime vouchers"

    voucher_service = VoucherService()
