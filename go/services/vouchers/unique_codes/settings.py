from django.conf import settings

SERVICE_URL = getattr(settings, 'UNIQUE_CODE_SERVICE_URL',
                      'http://127.0.0.1:7777')

FILE_FORMAT = ('unique_code', 'flavour')

UNIQUE_CODE_POOLS_PER_PAGE = getattr(
    settings, 'UNIQUE_CODE_POOLS_PER_PAGE', 25)
