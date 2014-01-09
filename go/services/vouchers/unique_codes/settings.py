from django.conf import settings

SERVICE_URL = getattr(settings, 'UNIQUE_CODE_SERVICE_URL',
                      'http://127.0.0.1:7777')
