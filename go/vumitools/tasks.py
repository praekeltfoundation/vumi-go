import json
from celery.task import task
from vumi.persist.txredis_manager import TxRedisManager

from go.base.command_utils import get_user_by_account_key
from go.base.utils import vumi_api, vumi_api_for_user
from go.config import get_conversation_definition
from go.vumitools.metrics import get_conversation_metric_prefix


@task(ignore_result=True)
def send_recent_conversation_metrics():
    conversation_keys = get_and_reset_recent_conversations()

    for conv_details in conversation_keys:
        details = json.loads(conv_details)
        user_api = get_user_api(details.account_key)
        conv = get_conversation(details.account_key, details.conv_key)
        publish_conversation_metrics(user_api, conv)


def get_and_reset_recent_conversations():
    # I'm not sure how to get the correct redis manager from here
    redis = TxRedisManager.from_config()
    conversation_keys = redis.getset("recent_coversations", )
    return conversation_keys


def get_user_api(self, user_account_key):
    user = get_user_by_account_key(user_account_key)
    return vumi_api_for_user(user)


def get_conversation(self, user_account_key, conversation_key):
    user_api = get_user_api(user_account_key)
    return user_api.get_conversation(conversation_key)


def publish_conversation_metrics(self, user_api, conversation):
    prefix = get_conversation_metric_prefix(conversation)
    metrics = vumi_api().get_metric_manager(prefix)

    conv_type = conversation.conversation_type
    conv_def = get_conversation_definition(conv_type, conversation)

    for metric in conv_def.get_metrics():
        value = metric.get_value(user_api)
        metrics.oneshot(metric.metric, value)

    metrics.publish_metrics()
