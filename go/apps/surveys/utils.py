from django.conf import settings
from vxpolls.manager import PollManager

from vumi.persist.redis_manager import RedisManager

redis = RedisManager.from_config(settings.VXPOLLS_REDIS_CONFIG)


def get_poll_config(poll_id):
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    config = pm.get_config(poll_id)
    config.update({
        'poll_id': poll_id,
    })

    config.setdefault('questions', [])
    config.setdefault('repeatable', True)
    config.setdefault('survey_completed_response',
                        'Thanks for completing the survey')
    return pm, config
