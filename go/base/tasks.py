import json
from celery.task import task

from go.base.utils import vumi_api
from go.config import get_conversation_definition
from go.vumitools.metrics import get_conversation_metric_prefix


@task(ignore_result=True)
def send_recent_conversation_metrics():
    api = vumi_api()
    try:
        conversation_details = get_and_reset_recent_conversations(api)

        for conv_details in conversation_details:
            details = json.loads(conv_details)
            user_api = api.get_user_api(details["account_key"])
            conv = user_api.get_conversation(
                details["account_key"], details["conv_key"])
            publish_conversation_metrics(vumi_api, user_api, conv)
    finally:
        api.close()


def get_and_reset_recent_conversations(vumi_api):
    redis = vumi_api.redis.sub_manager("conversation.metrics.middleware")

    # makes use of redis atomic functions to ensure nothing is added to the set
    # before it is deleted
    redis.rename("recent_coversations", "old_recent_conversations")
    conversation_details = redis.smembers("old_recent_conversations")
    redis.delete("old_recent_conversations")
    return conversation_details


def publish_conversation_metrics(vumi_api, user_api, conversation):
    prefix = get_conversation_metric_prefix(conversation)
    metrics = vumi_api.get_metric_manager(prefix)

    conv_type = conversation.conversation_type
    conv_def = get_conversation_definition(conv_type, conversation)

    for metric in conv_def.get_metrics():
        value = metric.get_value(user_api)
        metrics.oneshot(metric.metric, value)

    metrics.publish_metrics()
