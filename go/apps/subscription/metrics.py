from go.vumitools.metrics import ConversationMetric


class SubscriptionMetric(ConversationMetric):
    def __init__(self, conv, campaign_name):
        self.campaign_name = campaign_name
        metric_name = self.make_metric_name(campaign_name)
        super(SubscriptionMetric, self).__init__(conv, metric_name)

    @classmethod
    def make_metric_name(cls, campaign_name):
        return "%s.%s" % (campaign_name, cls.METRIC_NAME)

    def get_value(self, vumi_app, user_api):
        contacts = user_api.contact_store.contacts
        search = contacts.raw_search(
            "subscription-%s:%s" %
            (self.campaign_name, self.METRIC_NAME))

        return search.get_count()


class SubscribedMetric(SubscriptionMetric):
    METRIC_NAME = 'subscribed'


class UnsubscribedMetric(SubscriptionMetric):
    METRIC_NAME = 'unsubscribed'
