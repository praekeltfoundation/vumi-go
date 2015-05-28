from django.conf import settings

ENABLE_EVENT_STATUSES_IN_MESSAGE_LIST = getattr(
    settings, 'GO_ENABLE_EVENT_STATUSES_IN_MESSAGE_LIST', False)
