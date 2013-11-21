from go.vumitools.conversation.definition import ConversationDefinitionBase
from go.apps.subscription.metrics import SubscribedMetric, UnsubscribedMetric


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = u'subscription'

    def get_metrics(self):
        metrics = super(ConversationDefinition, self).get_metrics()

        campaign_names = sorted(set([
            h['campaign_name']
            for h in self.conv.config.get('handlers', [])]))

        metrics.extend([
            SubscribedMetric(self.conv, campaign_name)
            for campaign_name in campaign_names])

        metrics.extend([
            UnsubscribedMetric(self.conv, campaign_name)
            for campaign_name in campaign_names])

        return metrics
